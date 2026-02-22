import pandas_ta as ta
import numpy as np

def apply_strategy(df, ema_len=30, tp_mult=2.0, sl_mult=1.5):
    """
    SMC + CVD + Liquidity Sweep 전략 뼈대
    """
    # 1. ATR 계산 (동적 익절/손절용)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    # 동적 TP/SL 컬럼 생성
    df['target_tp'] = (df['ATR'] * tp_mult / df['close']).fillna(0.02).clip(lower=0.01)
    df['target_sl'] = (df['ATR'] * sl_mult / df['close']).fillna(0.015).clip(lower=0.008)

    # 2. 진입 로직 (이미 indicators.py에서 계산된 컬럼 활용)
    # 롱: VAL 하단 지지 + 다이버전스 + 수급(CVD) 유입
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    
    df['Long_Signal'] = (
        (df['close'] < df['VAL']) & 
        df['Bull_Div'] & 
        (df['CVD'] > df['CVD_Signal']) & 
        (df['close'] > ta.ema(df['close'], length=ema_len))
    )
    df['Long_Signal'] = df['Long_Signal'] & ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))

    # 숏: VAH 상단 저항 + 다이버전스 + 수급(CVD) 악화
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