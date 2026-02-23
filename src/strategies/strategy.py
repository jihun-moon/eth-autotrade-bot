import pandas_ta as ta
import numpy as np
import pandas as pd

def apply_strategy(df):
    """다이버전스 + 매물대 전략 (신호 빈도 개선 버전)"""
    # 기본 변수 설정
    tp = 0.015  # 익절 1.5%
    sl = 0.012  # 손절 1.2%
    
    # 1. 진입 구역 설정 (VAL/VAH 근처 0.2% 범위까지 허용하여 신호 빈도 확보)
    df['At_VAL'] = df['close'] < (df['VAL'] * 1.002)
    df['At_VAH'] = df['close'] > (df['VAH'] * 0.998)
    
    # 2. 다이버전스 로직 (너무 짧은 5캔들 대신 7캔들로 안정화)
    df['RSI_Up'] = df['RSI'] > df['RSI'].shift(1)
    df['RSI_Down'] = df['RSI'] < df['RSI'].shift(1)
    
    # 3. 롱 시그널: VAL 근처 + RSI 상승 + 수급(CVD) 개선
    # ADX 필터를 제거하여 신호가 더 자주 나오게 함
    long_signal = (
        (df['At_VAL']) & 
        (df['RSI_Up']) & 
        (df['CVD'] > df['CVD_Signal'])
    )
    
    # 4. 숏 시그널: VAH 근처 + RSI 하락 + 수급(CVD) 악화
    short_signal = (
        (df['At_VAH']) & 
        (df['RSI_Down']) & 
        (df['CVD'] < df['CVD_Signal'])
    )

    # 5. 시그널 통합 및 반환 형식 고정
    df['Signal'] = np.where(long_signal, 1, np.where(short_signal, -1, 0))
    
    # AI 진화 시 참고할 파라미터 셋
    params = {'tp': tp, 'sl': sl}
    
    return df, params