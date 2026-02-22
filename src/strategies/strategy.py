import pandas_ta as ta
import numpy as np

def apply_strategy(df, ema_len=30):
    # 1. 지표 계산 (ATR 필수)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    # [핵심] 백테스트용 시점별 동적 TP/SL 컬럼 생성
    # 각 봉마다 그 시점의 ATR을 기준으로 익절(2배) 및 손절(1.5배) 비율을 계산합니다.
    df['target_tp'] = (df['ATR'] * 2.0 / df['close']).fillna(0.02).clip(lower=0.015)
    df['target_sl'] = (df['ATR'] * 1.5 / df['close']).fillna(0.015).clip(lower=0.01)

    # 2. 진입 시그널 로직 (CVD, 매물대, 이평선 결합)
    # 롱 시그널
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    
    df['Long_Signal'] = (
        df['Below_Structure'] & df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal']) & 
        (df['close'] > ta.ema(df['close'], length=ema_len))
    )
    df['Long_Signal'] = df['Long_Signal'] & ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))

    # 숏 시그널
    df['Above_Structure'] = df['close'] > df['VAH']
    df['High_3'] = df['high'].rolling(3).max()
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))
    
    df['Short_Signal'] = (
        df['Above_Structure'] & df['Bear_Div'] & 
        (df['CVD'] < df['CVD_Signal']) & 
        (df['close'] < ta.ema(df['close'], length=ema_len))
    )
    df['Short_Signal'] = df['Short_Signal'] & ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))

    # 3. 실전(Live)용 현재 시점 파라미터 반환
    last_tp = df['target_tp'].iloc[-1]
    last_sl = df['target_sl'].iloc[-1]

    return df, {'tp': last_tp, 'sl': last_sl}