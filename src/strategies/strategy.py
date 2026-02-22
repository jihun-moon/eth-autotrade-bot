import pandas_ta as ta
import numpy as np

def apply_strategy(df, ema_len=30, tp_mult=2.0, sl_mult=1.5):
    """
    SMC(Volume Profile) + 수급(CVD) + 다이버전스 결합 전략
    """
    # 1. 지표 계산 (ATR 및 RSI)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['RSI'] = ta.rsi(df['close'], length=14)
    
    # 동적 TP/SL 컬럼 생성 (ATR 기반)
    df['target_tp'] = (df['ATR'] * tp_mult / df['close']).fillna(0.02).clip(lower=0.01)
    df['target_sl'] = (df['ATR'] * sl_mult / df['close']).fillna(0.015).clip(lower=0.008)

    # 2. 진입 시그널 로직
    # 롱 시그널: 매물대 하단 + 다이버전스 + 수급 개선
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    
    df['Long_Signal'] = (
        (df['close'] < df['VAL']) & 
        df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal']) & 
        (df['close'] > ta.ema(df['close'], length=ema_len))
    )
    df['Long_Signal'] = df['Long_Signal'] & ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))

    # 숏 시그널: 매물대 상단 + 다이버전스 + 수급 악화
    df['High_3'] = df['high'].rolling(3).max()
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))
    
    df['Short_Signal'] = (
        (df['close'] > df['VAH']) & 
        df['Bear_Div'] & 
        (df['CVD'] < df['CVD_Signal']) & 
        (df['close'] < ta.ema(df['close'], length=ema_len))
    )
    df['Short_Signal'] = df['Short_Signal'] & ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))

    # 3. 실전용 파라미터 반환
    last_tp = df['target_tp'].iloc[-1]
    last_sl = df['target_sl'].iloc[-1]

    return df, {'tp': last_tp, 'sl': last_sl}