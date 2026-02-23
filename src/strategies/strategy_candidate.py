import pandas as pd
import numpy as np

def apply_strategy(df):
    """15분봉 스윙 매매 최적화 전략: VAL/VAH + RSI 다이버전스 + CVD + EMA_200 트렌드 + ADX + Squeeze 필터"""
    
    # Parameters
    tp = 0.015   # 익절 1.5%
    sl = 0.012   # 손절 1.2%
    adx_thr = 20   # ADX 강도 기준 (20 이상)
    val_tol = 0.005   # VAL 허용 오차 0.5%
    vah_tol = 0.005   # VAH 허용 오차 0.5%
    rsi_long_min = 30   # RSI 상승 다이버전스 최소값
    rsi_short_max = 70   # RSI 하락 다이버전스 최대값
    
    # 초기화
    df['Signal'] = 0
    df['Entry_Timestamp'] = pd.NaT
    df['Entry_Price'] = np.nan
    df['Exit_Timestamp'] = pd.NaT
    
    # 트렌드 필터 (EMA_200)
    long_trend = (df['close'] < df['EMA_200'])
    short_trend = (df['close'] > df['EMA_200'])
    
    # 강도 필터 (ADX)
    adx_strong = (df['ADX'] > adx_thr)
    
    # 변동성 필터 (Squeeze)
    no_squeeze = (df['Squeeze_On'] == False)
    
    # VAL/VAH 구역
    long_val_zone = (df['close'] < df['VAL'] * (1 + val_tol))
    short_val_zone = (df['close'] > df['VAH'] * (1 - vah_tol))
    
    # RSI 다이버전스
    rsi_up = ((df['RSI'] > df['RSI'].shift(1)) & (df['RSI'] > rsi_long_min))
    rsi_down = ((df['RSI'] < df['RSI'].shift(1)) & (df['RSI'] < rsi_short_max))
    
    # CVD 필터
    long_cvd = (df['CVD'] > df['CVD_Signal'])
    short_cvd = (df['CVD'] < df['CVD_Signal'])
    
    # 이전 포지션 여부 (Signal이 0이어야 신규 진입)
    prev_signal = df['Signal'].shift(1)
    prev_zero = (prev_signal == 0)
    
    # 롱 시그널
    long_signal = (
        (prev_zero) &
        (no_squeeze) &
        (adx_strong) &
        (long_trend) &
        (long_val_zone) &
        (rsi_up) &
        (long_cvd)
    )
    
    # 숏 시그널
    short_signal = (
        (prev_zero) &
        (no_squeeze) &
        (adx_strong) &
        (short_trend) &
        (short_val_zone) &
        (rsi_down) &
        (short_cvd)
    )
    
    # 시그널 할당
    df['Signal'] = np.where(long_signal, 1,
                            np.where(short_signal, -1,
                                     df['Signal']))
    
    # Entry timestamp & price (첫 번째 비 0 시그널)
    entry_mask = (df['Signal'] != 0)
    df.loc[entry_mask, 'Entry_Timestamp'] = df.loc[entry_mask].index
    df.loc[entry_mask, 'Entry_Price'] = df.loc[entry_mask, 'close'].values
    
    # 이후 행에 진입 가격 전파
    df['Entry_Price'] = df['Entry_Price'].ffill()
    
    # Exit timestamp (TP / SL 도달 시)
    df['Exit_Timestamp'] = np.where(
        (df['Signal'] == 1) &
        (df['close'] >= df['Entry_Price'] * (1 + tp)),
        df.index,
        pd.NaT
    )
    
    df['Exit_Timestamp'] = np.where(
        (df['Signal'] == -1) &
        (df['close'] <= df['Entry_Price'] * (1 - sl)),
        df.index,
        df['Exit_Timestamp']
    )
    
    # 파라미터 반환
    params = {
        'tp': tp,
        'sl': sl,
        'adx_thr': adx_thr,
        'val_tol': val_tol,
        'vah_tol': vah_tol,
        'rsi_long_min': rsi_long_min,
        'rsi_short_max': rsi_short_max
    }
    
    return df, params