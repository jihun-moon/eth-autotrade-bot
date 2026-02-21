import pandas_ta as ta  # 누락된 임포트 추가

def apply_strategy(df, ema_len=30):
    # 1. 지훈님의 매물대 하단 낚시 조건 (파란 영역 하단 이탈 확인)
    df['Below_Structure'] = df['close'] < df['VAL']
    
    # 2. RSI 다이버전스 (최근 3캔들 기준 바닥 컨펌)
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    
    # 3. 최종 롱 시그널 조합
    df['Long_Signal'] = (
        df['Below_Structure'] & 
        df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal']) &  # 수급 개선 확인
        (df['close'] > ta.ema(df['close'], length=ema_len))  # 단기 추세 순응
    )
    return df