import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    """
    [다이버전스 Reversal + 추세 방어 전략]
    - VAL/VAH 외곽에서 RSI 다이버전스 발생 시 진입
    - ADX 및 EMA_200을 활용하여 강한 역추세장 진입 차단
    """
    # 필수 컬럼 체크 및 방어 로직
    required = ['close', 'low', 'high', 'RSI', 'VAL', 'VAH', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200']
    for col in required:
        if col not in df.columns:
            if col == 'RSI': df['RSI'] = ta.rsi(df['close'], length=14)
            if col == 'EMA_200': df['EMA_200'] = ta.ema(df['close'], length=200)
            if col == 'ADX': df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14']

    # =========================================
    # 1. 롱(Long) 타점: 매물대 하단 + 상승 다이버전스
    # =========================================
    df['Below_Structure'] = df['close'] < df['VAL']
    
    # 3개 캔들 기준 가격 저점 갱신 확인
    df['Low_3'] = df['low'].rolling(3).min()
    # 상승 다이버전스: 가격 저점은 갱신했으나 RSI는 상승 중
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    
    # 기본 진입 신호
    long_signal = (
        df['Below_Structure'] & 
        df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal']) &  
        (df['close'] > ta.ema(df['close'], length=ema_len))
    )
    
    # 🛡️ 추세 방어: 강한 하락 추세(ADX > 25 & 가격 < EMA_200)에서는 롱 진입 차단
    df['Long_Signal'] = long_signal & ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))

    # =========================================
    # 2. 숏(Short) 타점: 매물대 상단 + 하락 다이버전스
    # =========================================
    df['Above_Structure'] = df['close'] > df['VAH']
    
    # 3개 캔들 기준 가격 고점 갱신 확인
    df['High_3'] = df['high'].rolling(3).max()
    # 하락 다이버전스: 가격 고점은 갱신했으나 RSI는 하락 중
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))
    
    # 기본 진입 신호
    short_signal = (
        df['Above_Structure'] & 
        df['Bear_Div'] & 
        (df['CVD'] < df['CVD_Signal']) &  
        (df['close'] < ta.ema(df['close'], length=ema_len))
    )
    
    # 🛡️ 추세 방어: 강한 상승 추세(ADX > 25 & 가격 > EMA_200)에서는 숏 진입 차단
    df['Short_Signal'] = short_signal & ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))

    # =========================================
    # 3. 시스템 연동 데이터 생성 (포지션 및 TP/SL)
    # =========================================
    df['Signal'] = np.where(df['Long_Signal'], 1, np.where(df['Short_Signal'], -1, 0))
    
    # 진입 플래그 및 진입가 계산
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().shift(1).fillna(0)
    df['Entry_Flag'] = (df['Signal'] != 0) & (df['Position'] == 0)
    df['Entry_Price'] = np.where(df['Entry_Flag'], df['close'], np.nan)
    df['Entry_Price'] = df['Entry_Price'].ffill()
    
    # 동적 TP/SL 설정 (차트 및 실전 매매용)
    df['target_tp'] = tp
    df['target_sl'] = sl
    df['TP'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 + tp), df['Entry_Price'] * (1 - tp))
    df['SL'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 - sl), df['Entry_Price'] * (1 + sl))

    return df, {'tp': tp, 'sl': sl}