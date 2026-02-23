import pandas_ta as ta
import numpy as np
import pandas as pd

def apply_strategy(df):
    """15분봉 스윙 매매 최적화 전략 (다이버전스 + 매물대 + 트렌드 + 변동성)"""
    # 파라미터 설정
    tp = 0.015   # 익절 비율 1.5%
    sl = 0.012  # 손절 비율 1.2%
    
    # 1. 매물대 진입 허용 범위 (0.2% tolerance)
    df['At_VAL'] = (df['close'] < df['VAL'] * 1.002)
    df['At_VAH'] = (df['close'] > df['VAH'] * 0.998)
    
    # 2. 트렌드 필터 (EMA_200)
    df['Trend_Uptrend'] = (df['EMA_200'] > df['close'])
    df['Trend_Downtrend'] = (df['EMA_200'] < df['close'])
    
    # 3. RSI 다이버전스 (7캔들 연속 상승/하락)
    df['RSI_Up'] = (df['RSI'] > df['RSI'].shift(7))
    df['RSI_Down'] = (df['RSI'] < df['RSI'].shift(7))
    
    # 4. 변동성 필터 (Squeeze_On)
    df['No_Squeeze'] = (df['Squeeze_On'] == 0)
    
    # 5. 롱 시그널: 매물대 + 트렌드 + RSI 상승 + CVD 개선 + 저변동성
    long_signal = (
        (df['At_VAL']) &
        (df['Trend_Uptrend']) &
        (df['RSI_Up']) &
        (df['CVD'] > df['CVD_Signal']) &
        (df['No_Squeeze'])
    )
    
    # 6. 숏 시그널: 매물대 + 트렌드 + RSI 하락 + CVD 악화 + 저변동성
    short_signal = (
        (df['At_VAH']) &
        (df['Trend_Downtrend']) &
        (df['RSI_Down']) &
        (df['CVD'] < df['CVD_Signal']) &
        (df['No_Squeeze'])
    )
    
    # 7. 시그널 통합
    df['Signal'] = np.where(long_signal, 1, np.where(short_signal, -1, 0))
    
    # 8. 고정 TP/SL 레벨 (퍼센트 기준)
    df['TP'] = df['close'] * (1 + tp)
    df['SL'] = df['close'] * (1 - sl)
    
    # 9. 파라미터 반환
    params = {'tp': tp, 'sl': sl}
    return df, params