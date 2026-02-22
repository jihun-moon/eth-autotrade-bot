import pandas_ta as ta
import numpy as np
import pandas as pd

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    """다이버전스 + 매물대 상하단 전략"""
    # 1. 롱 타점: VAL 이탈 후 상승 다이버전스
    df['Below_Structure'] = df['close'] < (df['VAL'] * 1.001)
    df['Low_Lookback'] = df['low'].rolling(window=5).min()
    df['Bull_Div'] = (df['low'] <= df['Low_Lookback']) & (df['RSI'] > df['RSI'].shift(1))
    
    long_signal = (df['Below_Structure'] & df['Bull_Div'] & (df['CVD'] > df['CVD_Signal']))
    df['Long_Signal'] = long_signal & ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))

    # 2. 숏 타점: VAH 돌파 후 하락 다이버전스
    df['Above_Structure'] = df['close'] > (df['VAH'] * 0.999)
    df['High_Lookback'] = df['high'].rolling(window=5).max()
    df['Bear_Div'] = (df['high'] >= df['High_Lookback']) & (df['RSI'] < df['RSI'].shift(1))
    
    short_signal = (df['Above_Structure'] & df['Bear_Div'] & (df['CVD'] < df['CVD_Signal']))
    df['Short_Signal'] = short_signal & ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))

    # 3. 데이터 반환 형식 고정
    df['Signal'] = np.where(df['Long_Signal'], 1, np.where(df['Short_Signal'], -1, 0))
    return df, {'tp': tp, 'sl': sl}