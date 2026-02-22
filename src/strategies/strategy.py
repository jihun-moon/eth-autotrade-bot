import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    """
    [다이버전스 Reversal 전략] 
    - VAL/VAH 외곽에서 RSI 다이버전스가 발생할 때 진입
    - CVD 수급 방향성 확인으로 승률 극대화
    """
    # 필수 컬럼 체크
    required = ['close', 'low', 'high', 'RSI', 'VAL', 'VAH', 'CVD', 'CVD_Signal', 'EMA_200']
    for col in required:
        if col not in df.columns:
            # indicators.py에서 계산되지 않은 항목이 있을 경우 방어 코드
            if col == 'RSI': df['RSI'] = ta.rsi(df['close'], length=14)
            if col == 'EMA_200': df['EMA_200'] = ta.ema(df['close'], length=200)

    # =========================================
    # 1. 롱(Long) 타점: 매물대 하단 + 상승 다이버전스
    # =========================================
    df['Below_Structure'] = df['close'] < df['VAL']
    
    # 상승 다이버전스 (가격 저점은 낮아지거나 같은데, RSI는 상승)
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    
    df['Long_Signal'] = (
        df['Below_Structure'] & 
        df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal']) &  # 수급 개선 확인
        (df['close'] > ta.ema(df['close'], length=ema_len)) # 단기 추세 회복 확인
    )

    # =========================================
    # 2. 숏(Short) 타점: 매물대 상단 + 하락 다이버전스
    # =========================================
    df['Above_Structure'] = df['close'] > df['VAH']
    
    # 하락 다이버전스 (가격 고점은 높아지거나 같은데, RSI는 하락)
    df['High_3'] = df['high'].rolling(3).max()
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))
    
    df['Short_Signal'] = (
        df['Above_Structure'] & 
        df['Bear_Div'] & 
        (df['CVD'] < df['CVD_Signal']) &  # 수급 악화 확인
        (df['close'] < ta.ema(df['close'], length=ema_len)) # 단기 추세 이탈 확인
    )

    # =========================================
    # 3. 시스템 연동 데이터 생성
    # =========================================
    df['Signal'] = np.where(df['Long_Signal'], 1, np.where(df['Short_Signal'], -1, 0))
    
    # 포지션 및 진입가 계산 (VectorBT 및 실전 봇 호환)
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().shift(1).fillna(0)
    df['Entry_Flag'] = (df['Signal'] != 0) & (df['Position'] == 0)
    df['Entry_Price'] = np.where(df['Entry_Flag'], df['close'], np.nan)
    df['Entry_Price'] = df['Entry_Price'].ffill()
    
    # 목표가/손절가 설정
    df['TP'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 + tp), df['Entry_Price'] * (1 - tp))
    df['SL'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 - sl), df['Entry_Price'] * (1 + sl))

    return df, {'tp': tp, 'sl': sl}