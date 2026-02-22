import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    # 필수 컬럼 체크
    required = ['close', 'low', 'high', 'RSI', 'VAL', 'VAH', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200']
    for col in required:
        if col not in df.columns:
            if col == 'RSI': df['RSI'] = ta.rsi(df['close'], length=14)
            if col == 'EMA_200': df['EMA_200'] = ta.ema(df['close'], length=200)
            if col == 'ADX': df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14']

    # 1. 롱(Long) 타점 개선
    df['Below_Structure'] = df['close'] < (df['VAL'] * 1.001) # 약간의 마진 추가
    df['Low_Lookback'] = df['low'].rolling(5).min() # 3 -> 5로 확장
    df['Bull_Div'] = (df['low'] <= df['Low_Lookback']) & (df['RSI'] > df['RSI'].shift(1))
    
    # 🌟 EMA 조건을 가격 위치가 아닌 '방향성'으로 수정 (모순 해결)
    df['EMA_Short'] = ta.ema(df['close'], length=ema_len)
    long_signal = (
        df['Below_Structure'] & 
        df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal'])
    )
    df['Long_Signal'] = long_signal & ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))

    # 2. 숏(Short) 타점 개선
    df['Above_Structure'] = df['close'] > (df['VAH'] * 0.999)
    df['High_Lookback'] = df['high'].rolling(5).max()
    df['Bear_Div'] = (df['high'] >= df['High_Lookback']) & (df['RSI'] < df['RSI'].shift(1))
    
    short_signal = (
        df['Above_Structure'] & 
        df['Bear_Div'] & 
        (df['CVD'] < df['CVD_Signal'])
    )
    df['Short_Signal'] = short_signal & ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))

    # 3. 시스템 연동 데이터 생성
    df['Signal'] = np.where(df['Long_Signal'], 1, np.where(df['Short_Signal'], -1, 0))
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().shift(1).fillna(0)
    df['Entry_Flag'] = (df['Signal'] != 0) & (df['Position'] == 0)
    df['Entry_Price'] = np.where(df['Entry_Flag'], df['close'], np.nan)
    df['Entry_Price'] = df['Entry_Price'].ffill()
    
    # 🌟 TP/SL 계산식 수정 (Signal=0 일 때 NaN 처리)
    df['TP'] = np.select(
        [df['Signal'] == 1, df['Signal'] == -1],
        [df['Entry_Price'] * (1 + tp), df['Entry_Price'] * (1 - tp)],
        default=np.nan
    )
    df['SL'] = np.select(
        [df['Signal'] == 1, df['Signal'] == -1],
        [df['Entry_Price'] * (1 - sl), df['Entry_Price'] * (1 + sl)],
        default=np.nan
    )

    return df, {'tp': tp, 'sl': sl}