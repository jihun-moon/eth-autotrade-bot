import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    # 1. 롱(Long) 타점: 매물대 하단 + 다이버전스
    df['Below_Structure'] = df['close'] < (df['VAL'] * 1.001)
    df['Low_Lookback'] = df['low'].rolling(window=5).min()
    df['Bull_Div'] = (df['low'] <= df['Low_Lookback']) & (df['RSI'] > df['RSI'].shift(1))
    
    long_signal = (df['Below_Structure'] & df['Bull_Div'] & (df['CVD'] > df['CVD_Signal']))
    df['Long_Signal'] = long_signal & ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))

    # 2. 숏(Short) 타점: 매물대 상단 + 다이버전스
    df['Above_Structure'] = df['close'] > (df['VAH'] * 0.999)
    df['High_Lookback'] = df['high'].rolling(window=5).max()
    df['Bear_Div'] = (df['high'] >= df['High_Lookback']) & (df['RSI'] < df['RSI'].shift(1))
    
    short_signal = (df['Above_Structure'] & df['Bear_Div'] & (df['CVD'] < df['CVD_Signal']))
    df['Short_Signal'] = short_signal & ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))

    # 3. 시스템 연동 데이터
    df['Signal'] = np.where(df['Long_Signal'], 1, np.where(df['Short_Signal'], -1, 0))
    df['Entry_Price'] = pd.Series(np.where(df['Signal'] != 0, df['close'], np.nan), index=df.index).ffill()
    
    df['target_tp'], df['target_sl'] = tp, sl
    return df, {'tp': tp, 'sl': sl}