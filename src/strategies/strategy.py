import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    # 필수 컬럼 체크
    required = ['close', 'low', 'high', 'RSI', 'VAL', 'VAH', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200']
    for col in required:
        if col not in df.columns:
            if col == 'RSI': df[col] = ta.rsi(df['close'], length=14)
            if col == 'EMA_200': df[col] = ta.ema(df['close'], length=200)

    # VAL/VAH 이탈·복귀 감지 로직 개선
    # 최근 10캔들 이내에 VAL 아래로 내려간 적이 있었는지 체크
    df['Was_Below_VAL'] = (df['close'] < df['VAL']).rolling(window=10).max() > 0
    # 지금 막 VAL 위로 올라왔는지 체크
    df['Back_Above_VAL'] = (df['close'] > df['VAL']) & (df['close'].shift(1) <= df['VAL'])
    
    # 숏도 마찬가지
    df['Was_Above_VAH'] = (df['close'] > df['VAH']).rolling(window=10).max() > 0
    df['Back_Below_VAH'] = (df['close'] < df['VAH']) & (df['close'].shift(1) >= df['VAH'])

    # 최종 신호 결합
    df['Long_Signal'] = df['Was_Below_VAL'] & df['Back_Above_VAL'] & (df['CVD'] > df['CVD_Signal']) & (df['ADX'] >= 25)
    df['Short_Signal'] = df['Was_Above_VAH'] & df['Back_Below_VAH'] & (df['CVD'] < df['CVD_Signal']) & (df['ADX'] >= 25)

    # 시스템 연동 (기존 로직 유지)
    df['Signal'] = np.where(df['Long_Signal'], 1, np.where(df['Short_Signal'], -1, 0))
    df['Entry_Flag'] = (df['Signal'] != 0) & (df['Signal'].shift(1) == 0)
    df['Entry_Price'] = np.where(df['Entry_Flag'], df['close'], np.nan)
    df['Entry_Price'] = df['Entry_Price'].ffill()
    
    df['TP'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 + tp), 
               np.where(df['Signal'] == -1, df['Entry_Price'] * (1 - tp), np.nan))
    df['SL'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 - sl), 
               np.where(df['Signal'] == -1, df['Entry_Price'] * (1 + sl), np.nan))
    
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().shift(1).fillna(0)

    return df, {'tp': tp, 'sl': sl}