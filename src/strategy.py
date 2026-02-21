def apply_strategy(df):
    # 1. 추세 및 수급 필터
    df['Trend_OK'] = df['close'] > df['EMA_50']
    df['CVD_OK'] = df['CVD'] > df['CVD_Signal']
    df['Vol_OK'] = df['volume'] > ta.sma(df['volume'], length=20)
    
    # 2. RSI Bullish Divergence (간소화된 벡터 로직)
    # 최근 5캔들 저점 갱신 vs RSI 저점 상승 여부 확인
    df['Low_5'] = df['low'].rolling(5).min()
    df['RSI_Min_5'] = df['RSI'].rolling(5).min()
    
    # 다이버전스: 가격은 전저점보다 낮아졌는데, RSI는 전저점보다 높을 때
    df['Bull_Div'] = (df['low'] == df['Low_5']) & (df['RSI'] > df['RSI_Min_5'].shift(1))
    
    # 3. 최종 진입 시그널 (SMC Killzone 포함)
    df['Long_Signal'] = (
        df['Bull_Div'] & 
        df['Trend_OK'] & 
        df['CVD_OK'] & 
        df['Vol_OK'] & 
        (~df['Squeeze_On']) & 
        df['is_killzone']
    )
    
    # 4. 피보나치 목표가 계산용 Swing High/Low
    df['Swing_Low'] = df['low'].rolling(10).min()
    df['Swing_High'] = df['high'].rolling(10).max()
    
    return df