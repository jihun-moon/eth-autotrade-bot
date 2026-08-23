import numpy as np

def apply_strategy(df):
    """15분봉 스윙 매매 최적화 전략: VAL/VAH + RSI 다이버전스 + CVD + EMA_200 트렌드 + ADX + Squeeze 필터"""
    
    # 파라미터
    tp = 0.015  # 익절 1.5%
    sl = 0.012  # 손절 1.2%
    
    # 트렌드 필터 (EMA_200)
    long_trend = (df['close'] < df['EMA_200'])
    short_trend = (df['close'] > df['EMA_200'])
    
    # 강도 필터 (ADX)
    adx_strong = (df['ADX'] > 25)
    
    # 변동성 필터 (Squeeze_On)
    no_squeeze = (df['Squeeze_On'] == False)
    
    # 진입 구역 (VAL/VAH 허용 범위)
    long_val_zone = (df['close'] < df['VAL'] * 1.002)
    short_val_zone = (df['close'] > df['VAH'] * 0.998)
    
    # RSI 다이버전스
    rsi_up = (df['RSI'] > df['RSI'].shift(1))
    rsi_down = (df['RSI'] < df['RSI'].shift(1))
    
    # CVD 필터
    long_cvd = (df['CVD'] > df['CVD_Signal'])
    short_cvd = (df['CVD'] < df['CVD_Signal'])
    
    # 시그널 생성
    long_signal = (
        (no_squeeze) &
        (adx_strong) &
        (long_trend) &
        (long_val_zone) &
        (rsi_up) &
        (long_cvd)
    )
    
    short_signal = (
        (no_squeeze) &
        (adx_strong) &
        (short_trend) &
        (short_val_zone) &
        (rsi_down) &
        (short_cvd)
    )
    
    # Signal 컬럼 할당
    df['Signal'] = np.where(long_signal, 1, np.where(short_signal, -1, 0))
    
    # Entry Timestamp (df 인덱스가 datetime이면 그대로 사용)
    df['Entry_Timestamp'] = df.index
    
    # 파라미터 반환
    params = {'tp': tp, 'sl': sl}
    
    return df, params