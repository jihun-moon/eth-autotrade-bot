# -*- coding: utf-8 -*-
"""
diverge_structure_strategy.py

다이버전스 + 매물대(Structure) 돌파 전략
- VAL / VAH / CVD 가 이미 존재한다면 재계산하지 않음
- vectorbt 백테스트 시 leverage 를 사용하지 않고 risk_per_trade 로 포지션 사이징
- ATR 기반 동적 SL / TP 를 적용
- 모든 연산을 pandas / pandas_ta 로 벡터화

Author: Upstage Solar (Open 100B)
Date  : 2026‑02‑23
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta
from typing import Literal, Optional, Dict

# --------------------------------------------------------------
# 1️⃣ 지표·필터 계산 (필요 시 한 번만 계산)
# --------------------------------------------------------------
def _ensure_indicator(df: pd.DataFrame,
                     col: str,
                     length: int,
                     close_col: str = "close",
                     append: bool = True) -> pd.DataFrame:
    """이미 존재하면 반환, 없으면 pandas_ta 로 계산하고 반환."""
    if col in df.columns:
        return df
    # pandas_ta 가 자동으로 NaN을 채우지 않으므로 .fillna(0) 으로 초기화
    df = df.copy()
    df = df.ta.ta_func(
        col,
        length=length,
        close=close_col,
        append=append,
        # 예시: EMA, ADX, RSI, ATR, VAL, VAH, CVD 등은 각각 별도 함수
        # 여기서는 간단히 ta.ema, ta.adx, ta.rsi, ta.atr, ta.val, ta.vah, ta.cvd 를 사용
        # 실제 사용 시 적절히 교체
        # 예: df = df.ta.ema(length, close=close_col, append=append)
    )
    return df


def _compute_cvd_signal(df: pd.DataFrame,
                        cfd_len: int = 20,
                        close_col: str = "close",
                        append: bool = True) -> pd.DataFrame:
    """CVD와 같은 지표에 대한 ‘Signal’(예: SMA) 을 만든다."""
    if "CVD_Signal" in df.columns:
        return df
    df = df.copy()
    df = df.ta.sma(length=cfd_len, close=close_col, append=append)
    df.rename(columns={close_col: "CVD_Signal"}, inplace=True)
    return df


# --------------------------------------------------------------
# 2️⃣ 메인 전략 로직
# --------------------------------------------------------------
def generate_signals(
    df: pd.DataFrame,
    *,
    ema_len: int = 30,
    adx_len: int = 14,
    rsi_len: int = 14,
    atr_len: int = 14,
    low_lookback: int = 5,
    high_lookback: int = 5,
    val_offset: float = 0.001,
    vah_offset: float = 0.001,
    cfd_margin: float = 0.0,
    capital: float = 100_000.0,
    tp_factor: float = 0.02,   # TP = entry_price + tp_factor * ATR
    sl_factor: float = 0.015,  # SL = entry_price - sl_factor * ATR
    risk_per_trade: float = 0.01,   # 전체 자본의 % 로 포지션 사이즈 결정
    commission: float = 0.0005,
    slippage: float = 0.0005,
) -> tuple[pd.DataFrame, Dict[str, float]]:
    """
    다이버전스 + 매물대(Structure) 돌파 전략 신호 생성.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV 데이터가 들어있는 DataFrame.
    ema_len, adx_len, rsi_len, atr_len : int
        각각 EMA, ADX, RSI, ATR 계산에 사용되는 기간.
    low_lookback, high_lookback : int
        저점·고점 look‑back 윈도우.
    val_offset, vah_offset : float
        VAL/VAH 를 0.1% 정도 여유 있게 판정하기 위한 오프셋.
    cfd_margin : float
        CVD 와 CVD_Signal 간 비교 마진(예: 0 → 정확히 일치, 양수 → CVD > CVD_Signal 등).
    capital, risk_per_trade : float
        백테스트에 사용할 초기 자본·위험 비율.
    tp_factor, sl_factor : float
        ATR 기반 TP/SL 비율.
    commission, slippage : float
        백테스트 시 적용할 수수료·슬리피지 비율.

    Returns
    -------
    df : pd.DataFrame
        원본 DataFrame에 다음 컬럼이 추가된 형태:
        * EMA_<len>, ADX, RSI, ATR, VAL, VAH, CVD, CVD_Signal
        * Low_lookback, High_lookback
        * Long_Entry, Short_Entry, Signal, SL, TP, Exit
    settings : dict
        vectorbt.backtest 에 바로 넘겨줄 수 있는 설정 dict.
    """
    # ---------- 0️⃣ 기본 복사 ----------
    df = df.copy()

    # ---------- 1️⃣ 지표 계산 ----------
    # 1‑1) EMA(ema_len) – 매물대 구조 판단에 사용
    df = _ensure_indicator(df, "EMA_" + str(ema_len), ema_len, close_col="close", append=True)

    # 1‑2) ADX (trend filter)
    df = _ensure_indicator(df, "ADX", adx_len, close_col="close", append=True)

    # 1‑3) RSI (momentum)
    df = _ensure_indicator(df, "RSI", rsi_len, close_col="close", append=True)

    # 1‑4) ATR (SL/TP 계산 기반)
    df = _ensure_indicator(df, "ATR", atr_len, close_col="close", append=True)

    # 1‑5) VAL / VAH (이미 존재한다면 재계산 X)
    df = _ensure_indicator(df, "VAL", ema_len, close_col="close", append=True)
    df = _ensure_indicator(df, "VAH", ema_len, close_col="close", append=True)

    # 1‑6) CVD & CVD_Signal
    df = _ensure_indicator(df, "CVD", ema_len, close_col="close", append=True)
    df = _compute_cvd_signal(df, cfd_len=ema_len, close_col="close")

    # ---------- 2️⃣ 저점·고점 Look‑back ----------
    df["Low_lookback"] = df["low"].rolling(window=low_lookback).min()
    df["High_lookback"] = df["high"].rolling(window=high_lookback).max()

    # ---------- 3️⃣ 다이버전스 컬럼 ----------
    # Bull divergence (롱 진입)
    bull_div = (df["low"] <= df["Low_lookback"]) & (df["RSI"] > df["RSI"].shift(1))

    # Bear divergence (숏 진입)
    bear_div = (df["high"] >= df["High_lookback"]) & (df["RSI"] < df["RSI"].shift(1))

    # ---------- 4️⃣ 구조(Structure) 이탈/돌파 ----------
    below_structure = df["close"] < (df["VAL"] * (1.0 + val_offset))
    above_structure = df["close"] > (df["VAH"] * (1.0 - vah_offset))

    # ---------- 5️⃣ CVD 확인 (마진 적용) ----------
    #   * 롱: CVD > CVD_Signal + cfd_margin
    #   * 숏: CVD < CVD_Signal - cfd_margin
    long_cvd_ok = df["CVD"] > (df["CVD_Signal"] + cfd_margin)
    short_cvd_ok = df["CVD"] < (df["CVD_Signal"] - cfd_margin)

    # ---------- 6️⃣ 엔트리 시그널 ----------
    #   * 롱 : Below Structure + Bull Div + CVD OK + (ADX ≤ 25 OR close ≥ EMA_200)
    #   * 숏 : Above Structure + Bear Div + CVD OK + (ADX ≤ 25 OR close ≤ EMA_200)
    df["Long_Entry"] = (
        below_structure
        & bull_div
        & long_cvd_ok
        & ((df["ADX"] <= 25) | (df["close"] >= df["EMA_200"]))
    )

    df["Short_Entry"] = (
        above_structure
        & bear_div
        & short_cvd_ok
        & ((df["ADX"] <= 25) | (df["close"] <= df["EMA_200"]))
    )

    # ---------- 7️⃣ EMA_200 (전반적인 장기 추세) ----------
    df["EMA_200"] = df["close"].ta.ema(length=200, close="close", append=True).rename("EMA_200")

    # ---------- 8️⃣ 신호 통합 ----------
    # 1 = 롱, -1 = 숏, 0 = 평탄
    df["Signal"] = np.where(df["Long_Entry"], 1,
            np.where(df["Short_Entry"], -1, 0))

    # ---------- 9️⃣ ATR 기반 SL / TP ----------
    #   entry_price 를 전날 시그널 값(0)으로 보정 → NaN 방지
    entry_price = df["Signal"].shift(1).astype(int) * df["close"]
    df["SL"] = entry_price - sl_factor * df["ATR"]
    df["TP"] = entry_price + tp_factor * df["ATR"]

    # ---------- 🔟 청산(Exit) 로직 ----------
    #   * 롱 : 가격이 SL 이하 OR TP 도달
    #   * 숏 : 가격이 SL 이상 OR TP 도달
    long_exit = df["Signal"] == 1 & (df["close"] <= df["SL"]) | (df["close"] >= df["TP"])
    short_exit = df["Signal"] == -1 & (df["close"] >= df["SL"]) | (df["close"] <= df["TP"])

    #   * 평탄 상태(0)에서 진입/청산 전환 시 청산 신호 추가
    #   * 기존 시그널과 동일한 방향일 경우(연속 포지션) 기존 청산 조건을 그대로 적용
    df["Exit"] = (
        long_exit.astype(int) * 1 +
        short_exit.astype(int) * -1 +
        (df["Signal"] != df["Signal"].shift(1)).astype(int) * 0   # 무플랫 -> 플랫 전환 시 청산
    )

    # ---------- 1️⃣1️⃣ NaN 정리 ----------
    df = df.fillna(method="bfill").fillna(method="ffill")   # 초기 구간 NaN 방지

    # ---------- 1️⃣2️⃣ 백테스트용 설정 반환 ----------
    settings: Dict[str, float] = {
        "capital": capital,
        "commission": commission,
        "slippage": slippage,
        "risk_per_trade": risk_per_trade,
        # leverage 절대 금지 → 명시적으로 넣지 않음
    }

    return df, settings