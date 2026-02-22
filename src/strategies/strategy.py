import pandas_ta as ta
import numpy as np

def apply_strategy(df, ema_len=30):
    # 1. 롱(Long) 타점: 매물대 하단(VAL) 이탈 + 상승 다이버전스
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Low_Lookback'] = df['low'].rolling(window=3).min()
    df['Bull_Div'] = (df['low'] == df['Low_Lookback']) & (df['RSI'] > df['RSI'].shift(1))
    
    df['Long_Signal'] = (
        df['Below_Structure'] & 
        df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal']) &  
        (df['close'] > ta.ema(df['close'], length=ema_len))  
    )

    # 2. 숏(Short) 타점: 매물대 상단(VAH) 돌파 + 하락 다이버전스
    df['Above_Structure'] = df['close'] > df['VAH']
    df['High_Lookback'] = df['high'].rolling(window=3).max()
    df['Bear_Div'] = (df['high'] == df['High_Lookback']) & (df['RSI'] < df['RSI'].shift(1))
    
    df['Short_Signal'] = (
        df['Above_Structure'] & 
        df['Bear_Div'] & 
        (df['CVD'] < df['CVD_Signal']) &
        (df['close'] < ta.ema(df['close'], length=ema_len))
    )
    
    return df, {'tp': 0.02, 'sl': 0.015}