import pandas as pd
import numpy as np

def apply_strategy(df):
    """
    15분봉 스윙 매매용 다이버전스 + 매물대 + 보조지표 전략.
    개선 포인트:
    - VAL/VAH ±0.2% 근접 허용
    - RSI 다이버전스 (7캔들 안정화)
    - ADX, Squeeze, EMA_200, CVD, CVD_Signal, Volume 필터 적용
    - 고정 TP/SL (1.5%/1.2%) + EMA_200 기반 트레일링 스탑
    - 시그널 컬럼 (1=롱, -1=숏, 0=보류) 반환
    """
    # 기본 파라미터
    tp = 0.015   # 익절 1.5%
    sl = 0.012   # 손절 1.2%
    adx_thr = 20   # ADX 강도 기준
    squeeze_thr = 1   # Squeeze_On 필터
    volume_thr = 1.0   # Volume > EMA_Volume 필터

    # 1. 매물대 근접 여부 (VAL/VAH ±0.2%)
    df['At_VAL'] = df['close'] < (df['VAL'] * 1.002)
    df['At_VAH'] = df['close'] > (df['VAH'] * 0.998)

    # 2. RSI 다이버전스 (7캔들 안정화)
    df['RSI_Up'] = df['RSI'] > df['RSI'].shift(1)
    df['RSI_Down'] = df['RSI'] < df['RSI'].shift(1)

    # 3. 롱 진입 조건
    long_entry = (
        (df['At_VAL']) &
        (df['RSI_Up']) &
        (df['RSI'] > 30) &
        (df['RSI'] < 70) &
        (df['CVD'] > df['CVD_Signal']) &
        (df['ADX'] > adx_thr) &
        (df['Squeeze_On'] == squeeze_thr) &
        (df['EMA_200'] < df['close']) &
        (df['Volume'] > df['EMA_Volume'] * volume_thr)
    )

    # 4. 숏 진입 조건
    short_entry = (
        (df['At_VAH']) &
        (df['RSI_Down']) &
        (df['RSI'] < 30) &
        (df['RSI'] > 20) &
        (df['CVD'] < df['CVD_Signal']) &
        (df['ADX'] < adx_thr) &
        (df['Squeeze_On'] == squeeze_thr) &
        (df['EMA_200'] > df['close']) &
        (df['Volume'] < df['EMA_Volume'] * volume_thr)
    )

    # 5. 고정 TP/SL 및 트레일링 스탑 (EMA_200 기반)
    df['TP_Long'] = df['close'] * tp
    df['TP_Short'] = df['close'] * sl
    df['Trail_Long'] = df['EMA_200'] - (df['EMA_200'] * sl)
    df['Trail_Short'] = df['EMA_200'] + (df['EMA_200'] * sl)

    # 6. 종료 시그널 (TP/SL 도달, 트레일링 스탑, 추세 반전)
    df['Exit_Long'] = (
        (df['close'] >= df['TP_Long']) |
        (df['close'] <= df['Trail_Long']) |
        (df['close'] < df['EMA_200'])
    )
    df['Exit_Short'] = (
        (df['close'] <= df['TP_Short']) |
        (df['close'] >= df['Trail_Short']) |
        (df['close'] > df['EMA_200'])
    )

    # 7. 최종 진입 시그널 (진입 후 종료되지 않은 경우)
    df['Signal_Long'] = np.where(long_entry, 1, 0)
    df['Signal_Short'] = np.where(short_entry, -1, 0)
    df['Final_Long'] = np.where(df['Signal_Long'] == 1 & df['Exit_Long'] == 0, 1, 0)
    df['Final_Short'] = np.where(df['Signal_Short'] == -1 & df['Exit_Short'] == 0, -1, 0)
    df['Final_Signal'] = np.where(df['Final_Long'] == 1, 1,
                                 np.where(df['Final_Short'] == -1, -1, 0))

    # 파라미터 딕셔너리 반환
    params = {
        'tp': tp,
        'sl': sl,
        'adx_thr': adx_thr,
        'squeeze_thr': squeeze_thr,
        'volume_thr': volume_thr,
        'trend_long': 1,   # EMA_200 위에 있을 때
        'trend_short': 1   # EMA_200 아래에 있을 때
    }
    return df, params