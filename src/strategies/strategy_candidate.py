import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Tuple, Dict, Any

def apply_strategy(
    df: pd.DataFrame,
    ema_len: int = 30,
    atr_len: int = 14,
    tp_multiplier: float = 2.0,
    sl_multiplier: float = 1.5,
    min_tp: float = 0.015,
    min_sl: float = 0.01,
    cfd_len: int = 14,
    adx_len: int = 14,
    rsi_len: int = 14,
    val_len: int = 14,
    trailing_stop: bool = False,
    position_sizing: bool = False,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    매매 전략 적용 함수.

    Parameters
    ----------
    df : pd.DataFrame
        고(high), 저(low), 종가(close), 거래량(volume), datetime 컬럼을 포함한 DataFrame.
    ema_len : int, optional
        EMA 필터 길이 (기본값 30).
    atr_len : int, optional
        ATR 계산 길이 (기본값 14).
    tp_multiplier : float, optional
        익절 비율 (ATR 대비, 기본값 2.0).
    sl_multiplier : float, optional
        손절 비율 (ATR 대비, 기본값 1.5).
    min_tp : float, optional
        최소 익절 비율 (기본값 0.015).
    min_sl : float, optional
        최소 손절 비율 (기본값 0.01).
    cfd_len : int, optional
        CVD 계산 길이 (기본값 14).
    adx_len : int, optional
        ADX 계산 길이 (기본값 14).
    rsi_len : int, optional
        RSI 계산 길이 (기본값 14).
    val_len : int, optional
        Value Area Low/ High 계산 길이 (기본값 14).
    trailing_stop : bool, optional
        True이면 ATR 기반 트레일링 스탑 컬럼을 추가.
    position_sizing : bool, optional
        True이면 포지션 사이즈 컬럼을 추가.

    Returns
    -------
    Tuple[pd.DataFrame, Dict[str, float]]
        (전략 적용 후 DataFrame, {'tp': 마지막 익절 비율, 'sl': 마지막 손절 비율})
    """
    # 1️⃣ 필수 컬럼 검증
    required_cols = {"high", "low", "close", "volume", "datetime"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame에 필수 컬럼이 없습니다: {missing}")

    # 2️⃣ DataFrame 정렬 및 비어 있지 않은지 확인
    if df.empty:
        raise ValueError("입력 DataFrame이 비어 있습니다.")
    df = df.sort_index()  # datetime 인덱스가 있으면 정렬

    # 3️⃣ ATR 계산 (ATR 기반 TP/SL 비율 산출)
    df["ATR"] = ta.atr(df["high"], df["low"], df["close"], length=atr_len)

    # 4️⃣ TP/SL 비율 (ATR 기반) – 최소 비율 강제
    df["target_tp"] = (
        (df["ATR"] * tp_multiplier / df["close"])
        .fillna(min_tp)
        .clip(lower=min_tp)
    )
    df["target_sl"] = (
        (df["ATR"] * sl_multiplier / df["close"])
        .fillna(min_sl)
        .clip(lower=min_sl)
    )

    # 5️⃣ CVD, ADX, EMA_200, VAL, VAH, RSI, EMA 필터 계산
    df["CVD"] = ta.cvd(df["volume"], df["close"], length=cfd_len)
    # CVD 신호용 이동 평균 (5‑bar) – 기존 로직과 호환
    df["CVD_Signal"] = df["CVD"].rolling(5).mean().fillna(method="bfill")

    df["ADX"] = ta.adx(df["high"], df["low"], df["close"], length=adx_len)

    df["EMA_200"] = ta.ema(df["close"], length=200)
    df["EMA"] = ta.ema(df["close"], length=ema_len)

    df["VAL"] = ta.val(df["high"], df["low"], df["close"], length=val_len)
    df["VAH"] = ta.vah(df["high"], df["low"], df["close"], length=val_len)

    df["RSI"] = ta.rsi(df["close"], length=rsi_len)

    # 6️⃣ 롱 시그널 로직
    df["Below_Structure"] = df["close"] < df["VAL"]
    df["Low_3"] = df["low"].rolling(3).min()
    df["Bull_Div"] = (df["low"] == df["Low_3"]) & (df["RSI"] > df["RSI"].shift(1))

    df["Long_Signal"] = (
        df["Below_Structure"]
        & df["Bull_Div"]
        & (df["CVD"] > df["CVD_Signal"])
        & (df["close"] > df["EMA"])
    ) & ((df["ADX"] <= 25) | (df["close"] >= df["EMA_200"]))

    # 7️⃣ 숏 시그널 로직
    df["Above_Structure"] = df["close"] > df["VAH"]
    df["High_3"] = df["high"].rolling(3).max()
    df["Bear_Div"] = (df["high"] == df["High_3"]) & (df["RSI"] < df["RSI"].shift(1))

    df["Short_Signal"] = (
        df["Above_Structure"]
        & df["Bear_Div"]
        & (df["CVD"] < df["CVD_Signal"])
        & (df["close"] < df["EMA"])
    ) & ((df["ADX"] <= 25) | (df["close"] <= df["EMA_200"]))

    # 8️⃣ 트레일링 스탑 (옵션)
    if trailing_stop:
        # 현재 가격 - ATR * SL 비율 로 트레일링 스탑을 정의
        df["Trailing_Stop"] = df["close"] - df["ATR"] * sl_multiplier

    # 9️⃣ 포지션 사이즈 (옵션)
    if position_sizing:
        # 위험 비율 = (1 - SL) / SL 로 간단히 포지션 사이즈 산출
        df["Position_Size"] = (1 - df["target_sl"]) / df["target_sl"]

    # 🔟 마지막 TP/SL 비율 반환
    last_tp = df["target_tp"].iloc[-1]
    last_sl = df["target_sl"].iloc[-1]

    # 1️⃣1️⃣ 모든 수치 컬럼을 float 로 변환 (NaN 포함)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].astype(float)

    return df, {"tp": last_tp, "sl": last_sl}