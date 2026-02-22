import pandas_ta as ta

def apply_strategy(df, ema_len=30):
    # 1. 지표 계산 (ATR 필수 포함)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    # [기존 전략 로직]
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    
    df['Long_Signal'] = (
        df['Below_Structure'] & df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal']) & 
        (df['close'] > ta.ema(df['close'], length=ema_len))
    )
    df['Long_Signal'] = df['Long_Signal'] & ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))
    
    df['Above_Structure'] = df['close'] > df['VAH']
    df['High_3'] = df['high'].rolling(3).max()
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))
    
    df['Short_Signal'] = (
        df['Above_Structure'] & df['Bear_Div'] & 
        (df['CVD'] < df['CVD_Signal']) & 
        (df['close'] < ta.ema(df['close'], length=ema_len))
    )
    df['Short_Signal'] = df['Short_Signal'] & ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))

    # 2. 동적 파라미터 계산 (필수)
    last_atr = df['ATR'].iloc[-1] if 'ATR' in df.columns else 0.01
    last_close = df['close'].iloc[-1]
    d_tp = (last_atr * 2.0) / last_close
    d_sl = (last_atr * 1.5) / last_close

    # [중요] 반드시 (df, params_dict) 튜플을 반환
    return df, {'tp': max(d_tp, 0.02), 'sl': max(d_sl, 0.015)}