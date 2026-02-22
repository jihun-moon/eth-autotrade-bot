import pandas_ta as ta
import numpy as np

def apply_strategy(df, ema_len=30):
    """
    SMC + CVD + 추세 필터 결합 전략 (심플 버전)
    - 익절/손절은 고정(2%/1.5%)으로 가져가며 진입 시그널에 집중합니다.
    """
    # 1. 고정 익절/손절 설정 (복잡한 ATR 제거)
    df['target_tp'] = 0.02   # 2% 익절
    df['target_sl'] = 0.015  # 1.5% 손절

    # 2. 보조 지표 확인 (이미 indicators.py에서 계산됨)
    # EMA_200, ADX, VAL, VAH, CVD, CVD_Signal 사용
    
    # [필터] 강한 추세장에서의 역추세 진입 방어
    # - ADX가 25보다 크면 추세가 강하다고 판단
    strong_trend = df['ADX'] > 25
    uptrend = df['close'] > df['EMA_200']
    downtrend = df['close'] < df['EMA_200']

    # 3. 롱 시그널: 매물대 하단 + 수급 개선 + (하락 추세장 롱 금지)
    # 하락장(downtrend)이면서 추세가 강하면(strong_trend) 롱 진입을 차단합니다.
    long_filter = ~(strong_trend & downtrend)
    
    df['Long_Signal'] = (
        (df['close'] < df['VAL']) & 
        (df['CVD'] > df['CVD_Signal']) &
        long_filter
    )

    # 4. 숏 시그널: 매물대 상단 + 수급 악화 + (상승 추세장 숏 금지)
    # 상승장(uptrend)이면서 추세가 강하면(strong_trend) 숏 진입을 차단합니다.
    short_filter = ~(strong_trend & uptrend)
    
    df['Short_Signal'] = (
        (df['close'] > df['VAH']) & 
        (df['CVD'] < df['CVD_Signal']) &
        short_filter
    )

    # 5. 실전 및 백테스트용 규격 반환
    return df, {'tp': 0.02, 'sl': 0.015}