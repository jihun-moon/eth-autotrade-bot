import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    # 필수 컬럼 체크 및 누락 시 계산
    required = ['close', 'low', 'high', 'RSI', 'VAL', 'VAH', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200']
    for col in required:
        if col not in df.columns:
            if col == 'RSI':
                df['RSI'] = ta.rsi(df['close'], length=14)
            elif col == 'EMA_200':
                df['EMA_200'] = ta.ema(df['close'], length=200)

    # EMA_Short (가격 방향성)
    df['EMA_Short'] = ta.ema(df['close'], length=ema_len)

    # 저점/고점 Lookback
    df['Low_Lookback'] = df['low'].rolling(5).min()
    df['High_Lookback'] = df['high'].rolling(5).max()

    # RSI Divergence
    df['Bull_Div'] = (df['low'] <= df['Low_Lookback']) & (df['RSI'] > df['RSI'].shift(1))
    df['Bear_Div'] = (df['high'] >= df['High_Lookback']) & (df['RSI'] < df['RSI'].shift(1))

    # 가격 교차 조건 (이전 캔들 대비 VAL/VAH 위치)
    df['Prev_Close_Below_VAL'] = (df['close'].shift(1) < df['VAL'].shift(1) * 1.001).astype(bool)
    df['Prev_Close_Above_VAH'] = (df['close'].shift(1) > df['VAH'].shift(1) * 0.999).astype(bool)

    df['Close_Above_VAL'] = (df['close'] >= df['VAL'] * 1.001).astype(bool)
    df['Close_Below_VAH'] = (df['close'] <= df['VAH'] * 0.999).astype(bool)

    # CVD 방향성
    df['CVD_Up'] = (df['CVD'] > df['CVD_Signal']).astype(bool)
    df['CVD_Down'] = (df['CVD'] < df['CVD_Signal']).astype(bool)

    # EMA 방향성
    df['EMA_Up'] = (df['EMA_Short'] > df['EMA_200']).astype(bool)
    df['EMA_Down'] = (df['EMA_Short'] < df['EMA_200']).astype(bool)

    # ADX 조건 (추세 강도)
    df['ADX_Strength'] = (df['ADX'] > 20).astype(bool)

    # 롱 시그널: VAL 아래 → VAL 위로 복귀 + Bull_Div + CVD 상승 + EMA 상승 + ADX 강도
    df['Long_Signal'] = (
        df['Prev_Close_Below_VAL'] &
        df['Close_Above_VAL'] &
        df['Bull_Div'] &
        df['CVD_Up'] &
        df['EMA_Up'] &
        df['ADX_Strength']
    ).astype(bool)

    # 숏 시그널: VAH 위 → VAH 아래로 복귀 + Bear_Div + CVD 하락 + EMA 하락 + ADX 강도
    df['Short_Signal'] = (
        df['Prev_Close_Above_VAH'] &
        df['Close_Below_VAH'] &
        df['Bear_Div'] &
        df['CVD_Down'] &
        df['EMA_Down'] &
        df['ADX_Strength']
    ).astype(bool)

    # Signal 생성 (np.where → pd.Series)
    df['Signal'] = pd.Series(
        np.where(df['Long_Signal'], 1,
                np.where(df['Short_Signal'], -1, 0)),
        index=df.index
    ).ffill()

    # 포지션 계산 (shift + ffill)
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().shift(1).fillna(0)

    # 진입 플래그 및 진입 가격
    df['Entry_Flag'] = (df['Signal'] != 0) & (df['Position'] == 0)
    df['Entry_Price'] = pd.Series(
        np.where(df['Entry_Flag'], df['close'], np.nan),
        index=df.index
    ).ffill()

    # TP/SL 계산 (np.select → pd.Series)
    df['TP'] = pd.Series(
        np.select(
            [df['Signal'] == 1, df['Signal'] == -1],
            [df['Entry_Price'] * (1 + tp), df['Entry_Price'] * (1 - tp)],
            default=np.nan
        ),
        index=df.index
    )

    df['SL'] = pd.Series(
        np.select(
            [df['Signal'] == 1, df['Signal'] == -1],
            [df['Entry_Price'] * (1 - sl), df['Entry_Price'] * (1 + sl)],
            default=np.nan
        ),
        index=df.index
    )

    return df, {'tp': tp, 'sl': sl}