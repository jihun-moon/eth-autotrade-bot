def apply_strategy(df, ema_len=50, tp=0.02, sl=0.01):
    # 1. 지훈님의 매물대 하단 낚시 조건
    df['Below_Structure'] = df['close'] < df['VAL'] # 파란 영역 하단 밑
    
    # 2. RSI 다이버전스 (컨펌)
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    
    # 3. 최종 시그널
    df['Long_Signal'] = (
        df['Below_Structure'] & 
        df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal']) &
        (df['close'] > ta.ema(df['close'], length=ema_len)) # 추세 순응
    )
    return df