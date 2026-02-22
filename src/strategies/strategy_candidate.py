import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    # 필수 컬럼 체크
    required = ['close', 'low', 'high', 'RSI', 'VAL', 'VAH', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200']
    for col in required:
        if col not in df.columns:
            if col == 'RSI':
                df[col] = ta.rsi(df['close'], length=14)
            if col == 'EMA_200':
                df[col] = ta.ema(df['close'], length=200)

    # VAL/VAH 이탈·복귀 감지 로직
    df['Was_Below_VAL'] = (df['close'] < df['VAL']).rolling(window=10).max() > 0
    df['Back_Above_VAL'] = (df['close'] > df['VAL']) & (df['close'].shift(1) <= df['VAL'])

    df['Was_Above_VAH'] = (df['close'] > df['VAH']).rolling(window=10).max() > 0
    df['Back_Below_VAH'] = (df['close'] < df['VAH']) & (df['close'].shift(1) >= df['VAH'])

    # CVD 교차 (골든크로스 / 데드크로스)
    df['CVD_Cross'] = (
        (df['CVD'] > df['CVD_Signal']) & (df['CVD'].shift(1) <= df['CVD_Signal'].shift(1))
    ) | (
        (df['CVD'] < df['CVD_Signal']) & (df['CVD'].shift(1) >= df['CVD_Signal'].shift(1))
    )

    # ADX 기반 추세 방어 (가격이 EMA_200에서 2% 이상 벗어나면 진입 차단)
    df['Price_Dist'] = np.abs(df['close'] - df['EMA_200']) / df['EMA_200']
    df['Trend_Defense'] = (df['ADX'] >= 25) & (df['Price_Dist'] > 0.02)

    # 최종 신호 결합
    df['Long_Signal'] = (
        df['Was_Below_VAL'] &
        df['Back_Above_VAL'] &
        df['CVD_Cross'] &
        (~df['Trend_Defense'])
    )
    df['Short_Signal'] = (
        df['Was_Above_VAH'] &
        df['Back_Below_VAH'] &
        df['CVD_Cross'] &
        (~df['Trend_Defense'])
    )

    # 시스템 연동 (기존 로직 유지)
    df['Signal'] = np.where(df['Long_Signal'], 1,
                np.where(df['Short_Signal'], -1, 0)).astype(int)

    df['Entry_Flag'] = (df['Signal'] != 0) & (df['Signal'].shift(1) == 0).astype(int)
    df['Entry_Price'] = np.where(df['Entry_Flag'], df['close'], np.nan)
    df['Entry_Price'] = df['Entry_Price'].ffill()

    df['TP'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 + tp),
                np.where(df['Signal'] == -1, df['Entry_Price'] * (1 - tp), np.nan))
    df['SL'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 - sl),
                np.where(df['Signal'] == -1, df['Entry_Price'] * (1 + sl), np.nan))

    df['Position'] = df['Signal'].replace(0, np.nan).ffill().shift(1).fillna(0).astype(float)

    return df, {'tp': tp, 'sl': sl}