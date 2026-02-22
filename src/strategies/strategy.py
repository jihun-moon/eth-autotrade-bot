import pandas_ta as ta

def apply_strategy(df, ema_len=30):
    """
    Apply enhanced long/short entry signals with ADX and EMA_200 risk filters.
    """
    # 1. Long entry logic (with ADX/EMA_200 risk filter)
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    
    df['Long_Signal'] = (
        df['Below_Structure'] &
        df['Bull_Div'] &
        (df['CVD'] > df['CVD_Signal']) &
        (df['close'] > ta.ema(df['close'], length=ema_len))
    )
    
    # Block long entry when strong downtrend (ADX > 25 & close < EMA_200)
    df['Long_Signal'] = df['Long_Signal'] & (
        (df['ADX'] <= 25) | (df['close'] >= df['EMA_200'])
    )
    
    # 2. Short entry logic (with ADX/EMA_200 risk filter)
    df['Above_Structure'] = df['close'] > df['VAH']
    
    df['High_3'] = df['high'].rolling(3).max()
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))
    
    df['Short_Signal'] = (
        df['Above_Structure'] &
        df['Bear_Div'] &
        (df['CVD'] < df['CVD_Signal']) &
        (df['close'] < ta.ema(df['close'], length=ema_len))
    )
    
    # Block short entry when strong uptrend (ADX > 25 & close > EMA_200)
    df['Short_Signal'] = df['Short_Signal'] & (
        (df['ADX'] <= 25) | (df['close'] <= df['EMA_200'])
    )
    
    return df