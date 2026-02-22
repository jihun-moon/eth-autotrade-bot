import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    """
    개선된 가상화폐 퀀트 매매 전략.
    - 롱: 이전 캔들에서 VAL 아래에 있다가 현재 캔들에서 VAL 위로 복귀하고,
          CVD 상승, EMA_Short > EMA_200, ADX <= 25.
    - 숏: 이전 캔들에서 VAH 위에 있다가 현재 캔들에서 VAH 아래로 복귀하고,
          CVD 하락, EMA_Short < EMA_200, ADX <= 25.
    """
    # 1️⃣ 필수 컬럼이 없을 경우 계산 (이미 존재하면 재계산 금지)
    if 'RSI' not in df.columns:
        df['RSI'] = ta.rsi(df['close'], length=14)
    if 'EMA_200' not in df.columns:
        df['EMA_200'] = ta.ema(df['close'], length=200)
    if 'ADX' not in df.columns:
        df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14']

    # 2️⃣ EMA_Short (전략 전용) 계산
    if 'EMA_Short' not in df.columns:
        df['EMA_Short'] = ta.ema(df['close'], length=ema_len)

    # 3️⃣ Lookback 레벨 계산 (기존 로직 유지)
    df['Low_Lookback'] = df['low'].rolling(5).min()
    df['High_Lookback'] = df['high'].rolling(5).max()

    # 4️⃣ Bull / Bear Divergence (불리언 마스크 안전화)
    df['Bull_Div'] = (df['low'] <= df['Low_Lookback']) & (df['RSI'] > df['RSI'].shift(1)).astype(bool)
    df['Bear_Div'] = (df['high'] >= df['High_Lookback']) & (df['RSI'] < df['RSI'].shift(1)).astype(bool)

    # 5️⃣ 구조 위치 마스크
    df['Below_Structure'] = df['close'] < (df['VAL'] * 1.001)
    df['Above_Structure'] = df['close'] > (df['VAH'] * 0.999)

    # 6️⃣ 롱 시그널 (가격 복귀 + CVD 상승 + EMA 방향 + ADX)
    long_cond = (
        (df['close'].shift(1) < df['VAL'].shift(1)) &
        (df['close'] >= df['VAL']) &
        df['Bull_Div'] &
        (df['CVD'] > df['CVD'].shift(1)) &
        (df['EMA_Short'] > df['EMA_200']) &
        (df['ADX'] <= 25)
    )
    df['Long_Signal'] = long_cond

    # 7️⃣ 숏 시그널 (가격 복귀 + CVD 하락 + EMA 방향 + ADX)
    short_cond = (
        (df['close'].shift(1) > df['VAH'].shift(1)) &
        (df['close'] <= df['VAH']) &
        df['Bear_Div'] &
        (df['CVD'] < df['CVD'].shift(1)) &
        (df['EMA_Short'] < df['EMA_200']) &
        (df['ADX'] <= 25)
    )
    df['Short_Signal'] = short_cond

    # 8️⃣ 전체 시그널 (Long=+1, Short=-1, No=0)
    df['Signal'] = pd.Series(
        np.where(df['Long_Signal'], 1,
                np.where(df['Short_Signal'], -1, 0)),
        index=df.index
    )

    # 9️⃣ 포지션 컬럼 생성 (NaN → NaN, 0 → NaN, ffill, shift, fillna)
    df['Position'] = (
        df['Signal'].replace(0, np.nan).ffill()
        .shift(1).fillna(0)
    )

    # 🔟 진입 플래그 (시그널이 발생하고 포지션이 없을 때)
    df['Entry_Flag'] = (df['Signal'] != 0) & (df['Position'] == 0)

    # 1️⃣1️⃣ 진입 가격 (NaN → NaN, ffill)
    df['Entry_Price'] = pd.Series(
        np.where(df['Entry_Flag'], df['close'], np.nan),
        index=df.index
    ).ffill()

    # 1️⃣2️⃣ TP / SL 계산 (np.select → Series → ffill)
    df['TP'] = pd.Series(
        np.select(
            [df['Signal'] == 1, df['Signal'] == -1],
            [df['Entry_Price'] * (1 + tp), df['Entry_Price'] * (1 - tp)],
            default=np.nan
        ),
        index=df.index
    ).ffill()

    df['SL'] = pd.Series(
        np.select(
            [df['Signal'] == 1, df['Signal'] == -1],
            [df['Entry_Price'] * (1 - sl), df['Entry_Price'] * (1 + sl)],
            default=np.nan
        ),
        index=df.index
    ).ffill()

    return df, {'tp': tp, 'sl': sl}