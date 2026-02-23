import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df):
    """15분봉 스윙 매매 최적화 전략: VAL/VAH + RSI 다이버전스 + CVD + EMA_200 트렌드 + ADX + Squeeze 필터
    + BollingerBand, ATR 기반 SL, Volume 필터, MACD 모멘텀, POC 스윙 포인트 확인"""
    
    # Parameters
    tp = 0.015  # 익절 1.5%
    sl = 0.012  # 손절 1.2%
    
    # EMA_200 trend (multi‑timeframe buffer)
    long_trend = (df['close'] > df['EMA_200'] * 1.0005)
    short_trend = (df['close'] < df['EMA_200'] * 0.9995)

    # ADX strength filter
    adx_strong = (df['ADX'] > 25)

    # Squeeze filter (no squeeze)
    no_squeeze = (df['Squeeze_On'] == False)

    # VAL/VAH zone filter (entry within 0.2% of VAL for long, 0.2% of VAH for short)
    long_val_zone = (df['close'] < df['VAL'] * 1.002)
    short_val_zone = (df['close'] > df['VAH'] * 0.998)

    # RSI divergence filter (RSI direction matches price direction)
    rsi_up = (df['RSI'] > df['RSI'].shift(1))
    rsi_down = (df['RSI'] < df['RSI'].shift(1))
    price_up = (df['close'] > df['close'].shift(1))
    price_down = (df['close'] < df['close'].shift(1))
    long_rsi_div = (rsi_up & price_up)
    short_rsi_div = (rsi_down & price_down)

    # CVD filter
    long_cvd = (df['CVD'] > df['CVD_Signal'])
    short_cvd = (df['CVD'] < df['CVD_Signal'])

    # Bollinger Band filter (avoid extreme bands)
    bb_df = df['close'].ta.bbands(length=20, std=2)
    bb_ok_long = (df['close'] > bb_df['bb_bb_lower'] * 0.99)
    bb_ok_short = (df['close'] < bb_df['bb_bb_upper'] * 1.01)

    # ATR 기반 동적 손절 레벨
    df['ATR'] = df['close'].ta.atr(length=14)
    df['SL_long'] = df['close'] * (1 - sl)   # 손절 라인 (가격 * (1 - sl))
    df['SL_short'] = df['close'] * (1 + sl)  # 손절 라인 (가격 * (1 + sl))

    # Volume filter (average 20‑period volume)
    df['vol_avg'] = df['volume'].ta.sma(length=20)
    long_vol = (df['volume'] > df['vol_avg'] * 1.2)
    short_vol = (df['volume'] < df['vol_avg'] * 0.8)

    # MACD 필터 (모멘텀 확인)
    macd_df = df['close'].ta.macd(fast=12, slow=26, signal=9)
    macd_cross_up = (macd_df['macd'] > macd_df['macd_signal'])
    macd_cross_down = (macd_df['macd'] < macd_df['macd_signal'])

    # POC 필터 (최근 스윙 포인트 근접 여부)
    long_poc = (df['close'] < df['POC'])
    short_poc = (df['close'] > df['POC'])

    # 최종 시그널 조합
    long_signal = (
        (no_squeeze) &
        (adx_strong) &
        (long_trend) &
        (long_val_zone) &
        (long_rsi_div) &
        (long_cvd) &
        (bb_ok_long) &
        (long_vol) &
        (macd_cross_up) &
        (long_poc)
    )
    short_signal = (
        (no_squeeze) &
        (adx_strong) &
        (short_trend) &
        (short_val_zone) &
        (short_rsi_div) &
        (short_cvd) &
        (bb_ok_short) &
        (short_vol) &
        (macd_cross_down) &
        (short_poc)
    )

    # Signal 컬럼 할당
    df['Signal'] = np.where(long_signal, 1,
                            np.where(short_signal, -1, 0))

    # Entry timestamp
    df['Entry_Timestamp'] = df.index

    # 파라미터 반환
    params = {'tp': tp, 'sl': sl}
    return df, params