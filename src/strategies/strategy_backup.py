import pandas_ta as ta

def apply_strategy(df, ema_len=30):
    # =========================================
    # 1. 롱(Long) 타점 전략 (기존 동일)
    # =========================================
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    
    df['Long_Signal'] = (
        df['Below_Structure'] & 
        df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal']) &  
        (df['close'] > ta.ema(df['close'], length=ema_len))  
    )

    # =========================================
    # 2. 숏(Short) 타점 전략 (롱의 정반대)
    # =========================================
    # 매물대 상단(VAH) 위로 올라갔다가 저항받는 자리
    df['Above_Structure'] = df['close'] > df['VAH']
    
    # RSI 하락 다이버전스 (고점은 같거나 높아지는데 RSI는 꺾임)
    df['High_3'] = df['high'].rolling(3).max()
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))
    
    df['Short_Signal'] = (
        df['Above_Structure'] & 
        df['Bear_Div'] & 
        (df['CVD'] < df['CVD_Signal']) &                     # 수급 악화 (매도세 우위)
        (df['close'] < ta.ema(df['close'], length=ema_len))  # 단기 이평선 아래로 꺾임 (하락 추세)
    )
    
    return df