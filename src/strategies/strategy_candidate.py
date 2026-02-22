import pandas as pd
import pandas_ta as ta
import numpy as np

def apply_strategy(df: pd.DataFrame, ema_len: int = 30) -> tuple[pd.DataFrame, dict]:
    """
    개선된 매매 전략
    - indicators.py에서 이미 계산된 VAL, VAH, CVD, ADX, EMA_200을 활용
    - 다이버전스와 수급(CVD)을 결합하여 시그널 생성
    - ADX와 EMA_200을 리스크 필터로 사용하여 역추세 진입 방지
    """
    # 1. 진입용 EMA 계산 (기존 컬럼과 겹치지 않게 'EMA_Signal'로 명명)
    df['EMA_Signal'] = ta.ema(df['close'], length=ema_len)

    # 2. 구조 기반 상태 정의 (VAL, VAH는 indicators.py에 이미 있음)
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Above_Structure'] = df['close'] > df['VAH']

    # 3. 다이버전스 로직 (Low_3 / High_3 활용)
    df['Low_3'] = df['low'].rolling(3).min()
    df['High_3'] = df['high'].rolling(3).max()
    
    # Bull / Bear divergence
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))

    # 4. 롱 / 숏 시그널 생성
    # 롱 시그널: 저평가 구간 + 상승 다이버전스 + 수급 개선 + 단기 이평 상회
    # 리스크 필터: 추세가 약하거나(ADX <= 25) 장기 추세가 상승(EMA_200 위)일 때만 허용
    df['Long_Signal'] = (
        df['Below_Structure'] &
        df['Bull_Div'] &
        (df['CVD'] > df['CVD_Signal']) &
        (df['close'] > df['EMA_Signal'])
    ) & ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))

    # 숏 시그널: 고평가 구간 + 하락 다이버전스 + 수급 악화 + 단기 이평 하회
    # 리스크 필터: 추세가 약하거나 장기 추세가 하락(EMA_200 아래)일 때만 허용
    df['Short_Signal'] = (
        df['Above_Structure'] &
        df['Bear_Div'] &
        (df['CVD'] < df['CVD_Signal']) &
        (df['close'] < df['EMA_Signal'])
    ) & ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))

    # 5. 최종 반환 (고정 TP/SL)
    # 시스템 규격에 맞춰 (df, params_dict) 형태 유지
    return df, {'tp': 0.02, 'sl': 0.015}