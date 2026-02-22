import pandas_ta as ta
import numpy as np
import pandas as pd

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    """양방향 다이버전스 + 매물대 전략"""
    # 1. 롱(Long) 타점: VAL 하단 이탈 + 상승 다이버전스
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Low_Lookback'] = df['low'].rolling(window=5).min()
    df['Bull_Div'] = (df['low'] <= df['Low_Lookback']) & (df['RSI'] > df['RSI'].shift(1))
    
    long_signal = (
        df['Below_Structure'] & 
        df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal'])
    )
    df['Long_Signal'] = long_signal & ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))

    # 2. 숏(Short) 타점: VAH 상단 돌파 + 하락 다이버전스
    df['Above_Structure'] = df['close'] > df['VAH']
    df['High_Lookback'] = df['high'].rolling(window=5).max()
    df['Bear_Div'] = (df['high'] >= df['High_Lookback']) & (df['RSI'] < df['RSI'].shift(1))
    
    short_signal = (
        df['Above_Structure'] & 
        df['Bear_Div'] & 
        (df['CVD'] < df['CVD_Signal'])
    )
    df['Short_Signal'] = short_signal & ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))

    # 3. 시스템 연동 데이터 생성
    df['Signal'] = np.where(df['Long_Signal'], 1, np.where(df['Short_Signal'], -1, 0))
    df['Entry_Price'] = pd.Series(np.where(df['Signal'] != 0, df['close'], np.nan), index=df.index).ffill()
    
    return df, {'tp': tp, 'sl': sl}