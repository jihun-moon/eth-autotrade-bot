import pandas_ta as ta

def apply_strategy(df, ema_len=30):
    """
    기존 롱/숏 진입 로직에 ADX와 EMA_200 기반 리스크 관리 필터를 추가한 전략 함수.
    
    - 강한 상승 추세(ADX > 25 & close > EMA_200)에서는 숏 진입을 차단.
    - 강한 하락 추세(ADX > 25 & close < EMA_200)에서는 롱 진입을 차단.
    - 기존 VAL/VAH, 다이버전스(Bull_Div/Bear_Div) 로직은 그대로 유지.
    """
    
    # ==============================
    # 1. 롱(Long) 타점 전략
    # ==============================
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    
    # 기존 롱 진입 조건
    long_base = (
        df['Below_Structure'] &
        df['Bull_Div'] &
        (df['CVD'] > df['CVD_Signal']) &
        (df['close'] > ta.ema(df['close'], length=ema_len))
    )
    
    # 강한 하락 추세(ADX > 25 & close < EMA_200)에서는 롱 진입 차단
    strong_downtrend = (df['ADX'] > 25) & (df['close'] < df['EMA_200'])
    df['Long_Signal'] = long_base & ~strong_downtrend
    
    # ==============================
    # 2. 숏(Short) 타점 전략
    # ==============================
    df['Above_Structure'] = df['close'] > df['VAH']
    df['High_3'] = df['high'].rolling(3).max()
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))
    
    # 기존 숏 진입 조건
    short_base = (
        df['Above_Structure'] &
        df['Bear_Div'] &
        (df['CVD'] < df['CVD_Signal']) &
        (df['close'] < ta.ema(df['close'], length=ema_len))
    )
    
    # 강한 상승 추세(ADX > 25 & close > EMA_200)에서는 숏 진입 차단
    strong_uptrend = (df['ADX'] > 25) & (df['close'] > df['EMA_200'])
    df['Short_Signal'] = short_base & ~strong_uptrend
    
    return df