import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(
    df: pd.DataFrame,
    ema_len: int = 30,
    adx_len: int = 14,
    rsi_len: int = 14,
    val_volume_pct: float = 0.7,
    val_end_pct: float = 0.9,
    low_lookback: int = 5,
    high_lookback: int = 5,
    cvd_signal_len: int = 20,
    adx_thresh: float = 25,
    tp: float = 0.02,
    sl: float = 0.015,
) -> tuple[pd.DataFrame, dict]:
    """
    개선된 퀀트 매매 전략.
    - VAL/VAH (Value Area Low/High) 를 직접 계산.
    - 저점/고점 갱신 시 RSI 상승/하락을 이용한 다이버전스 강화.
    - CVD (Close‑Open) * Volume 로 수급 필터 적용.
    - ADX 기반 추세 방어 로직 포함.
    - 불리언 연산 시 astype(bool) 사용, np.where 로 numpy 배열 처리 후 ffill().
    """
    # 기본 지표
    df["RSI"] = ta.rsi(df["close"], length=rsi_len)
    df["EMA"] = ta.ema(df["close"], length=ema_len)
    df["ADX"] = ta.adx(df["high"], df["low"], df["close"], length=adx_len)

    # CVD (Close‑Open) * Volume
    df["CVD"] = (df["close"] - df["open"]) * df["volume"]
    df["CVD_Signal"] = ta.ema(df["CVD"], length=cvd_signal_len)

    # Value Area Low / High (70%~90% 누적 거래량 구간)
    total_vol = df["volume"].sum()
    cum_vol = df["volume"].cumsum()
    val_start = cum_vol >= total_vol * val_volume_pct
    val_end   = cum_vol >= total_vol * val_end_pct

    df["VAL"] = np.nan
    df["VAH"] = np.nan
    df.loc[val_start & val_end, "VAL"] = df.loc[val_start & val_end, "low"].min()
    df.loc[val_start & val_end, "VAH"] = df.loc[val_start & val_end, "high"].max()
    df["VAL"] = df["VAL"].ffill()
    df["VAH"] = df["VAH"].ffill()

    # 저점/고점 갱신 다이버전스
    df["Low_Lookback"] = df["low"].rolling(window=low_lookback).min()
    df["High_Lookback"] = df["high"].rolling(window=high_lookback).max()

    # Bullish / Bearish divergence (np.where → ffill)
    df["Bull_Div"] = pd.Series(
        np.where(
            (df["low"] == df["Low_Lookback"]) & (df["RSI"] > df["RSI"].shift(1)),
            1,
            0,
        ),
        index=df.index,
    ).ffill()

    df["Bear_Div"] = pd.Series(
        np.where(
            (df["high"] == df["High_Lookback"]) & (df["RSI"] < df["RSI"].shift(1)),
            1,
            0,
        ),
        index=df.index,
    ).ffill()

    # 매물대 활용 (VAL / VAH)
    df["Below_Structure"] = (df["close"] < df["VAL"]).astype(bool)
    df["Above_Structure"] = (df["close"] > df["VAH"]).astype(bool)

    # 가격 교차 신호 (역추세 진입 방지)
    df["Long_Cross"] = (df["close"] > df["VAL"]) & (~df["close"].shift(1) > df["VAL"])
    df["Short_Cross"] = (df["close"] < df["VAH"]) & (~df["close"].shift(1) < df["VAH"])

    # ADX 기반 동적 필터 (ADX < 25 기본, ADX가 낮을 경우 완화)
    df["ADX_Threshold"] = np.where(df["ADX"] < 15, 20, adx_thresh)
    df["Dynamic_ADX_Threshold"] = df["ADX_Threshold"].ffill()

    # 최종 시그널
    df["Long_Signal"] = (
        df["Long_Cross"]
        & df["Bull_Div"]
        & (df["CVD"] > df["CVD_Signal"])
        & (df["close"] > df["EMA"])
        & (df["ADX"] < df["Dynamic_ADX_Threshold"])
    )

    df["Short_Signal"] = (
        df["Short_Cross"]
        & df["Bear_Div"]
        & (df["CVD"] < df["CVD_Signal"])
        & (df["close"] < df["EMA"])
        & (df["ADX"] < df["Dynamic_ADX_Threshold"])
    )

    # NaN 제거 (필요 시)
    df = df.dropna(subset=["Long_Signal", "Short_Signal"])

    return df, {"tp": tp, "sl": sl}