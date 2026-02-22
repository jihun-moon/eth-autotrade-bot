import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Dict, Any, Optional

def apply_strategy(
    df: pd.DataFrame,
    *,
    ema_len: int = 30,
    atr_len: int = 14,
    tp_mult: float = 2.0,
    sl_mult: float = 1.5,
    tp_min: float = 0.015,
    sl_min: float = 0.010,
    tp_max: float = 0.20,
    sl_max: float = 0.10,
    use_cvd: bool = True,
    use_adx: bool = True,
    use_ema_200: bool = True,
    use_val_vah: bool = True,
    use_rsi: bool = True,
    use_cvd_signal: bool = True,
    use_adx_filter: bool = True,
    use_ema_200_filter: bool = True,
    use_val_vah_filter: bool = True,
    use_rsi_filter: bool = True,
) -> tuple[pd.DataFrame, Dict[str, float]]:
    """
    매매 전략 적용 함수

    Parameters
    ----------
    df : pd.DataFrame
        백테스트용 OHLCV 데이터프레임. 최소 컬럼:
        - high, low, close
        - VAL, VAH (지지·저항 레벨)
        - CVD, CVD_Signal (거래량·가격 변동 지표)
        - ADX, EMA_200, RSI (선택 컬럼)
    ema_len : int, default 30
        진입·청산에 사용할 EMA 길이
    atr_len : int, default 14
        ATR 계산에 사용할 기간
    tp_mult : float, default 2.0
        목표 익절 비율 = ATR × tp_mult / 현재가
    sl_mult : float, default 1.5
        목표 손절 비율 = ATR × sl_mult / 현재가
    tp_min / sl_min : float, default 0.015 / 0.010
        최소 TP/SL 비율 (절대값)
    tp_max / sl_max : float, default 0.20 / 0.10
        최대 TP/SL 비율 (절대값)
    use_* : bool, default True
        각 보조 지표( CVD, ADX, EMA_200, VAL/VAH, RSI 등 )를
        전략에 포함할지 여부. False 로 설정하면 해당 컬럼을
        무시하고 기존 컬럼이 있으면 그대로 사용합니다.
    use_cvd_signal : bool, default True
        CVD와 CVD_Signal을 이용한 “CVD 교차” 필터 사용 여부
    use_adx_filter : bool, default True
        ADX ≤ 25 (추세 약함) 필터 사용 여부
    use_ema_200_filter : bool, default True
        EMA_200 위/아래 필터 사용 여부
    use_val_vah_filter : bool, default True
        VAL/VAH 레벨 위·아래 필터 사용 여부
    use_rsi_filter : bool, default True
        RSI 상승·하락 다이버전스 필터 사용 여부

    Returns
    -------
    df : pd.DataFrame
        원본 DataFrame에 아래 컬럼이 추가된 결과:
        - ATR, target_tp, target_sl
        - Below_Structure / Above_Structure
        - Bull_Div / Bear_Div
        - Long_Signal / Short_Signal
    dict
        {'tp': last_tp, 'sl': last_sl} – 현재 시점(마지막 행)의
        목표 TP/SL 비율 (float 혹은 np.nan)

    Notes
    -----
    * 모든 보조 지표는 **NaN**을 `fillna` 로 대체한 뒤
      `astype(bool)` 로 boolean 컬럼을 만든다.
    * TP/SL 비율은 `clip` 으로 최소·최대값을 강제한다.
    * `use_*` 플래그가 False 일 경우 해당 컬럼이 없으면
      자동으로 `fillna(False)` 로 처리한다.
    * `use_ema_200` 가 True 이고 EMA_200 컬럼이 없을 경우
      내부에서 EMA_200을 계산한다.
    """

    # ------------------------------------------------------------------
    # 1️⃣ ATR 계산 (필수)
    # ------------------------------------------------------------------
    df = df.copy()  # SettingWithCopy 방지
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=atr_len)

    # ------------------------------------------------------------------
    # 2️⃣ 목표 TP / SL (ATR 기반, 배수는 인자)
    # ------------------------------------------------------------------
    df['target_tp'] = (df['ATR'] * tp_mult / df['close']).fillna(0.02)
    df['target_sl'] = (df['ATR'] * sl_mult / df['close']).fillna(0.015)

    # 최소·최대 비율 강제
    df['target_tp'] = df['target_tp'].clip(lower=tp_min, upper=tp_max)
    df['target_sl'] = df['target_sl'].clip(lower=sl_min, upper=sl_max)

    # ------------------------------------------------------------------
    # 3️⃣ 보조 지표(옵션) – 필요 시 자동 계산
    # ------------------------------------------------------------------
    # EMA_200
    if use_ema_200 and 'EMA_200' not in df.columns:
        df['EMA_200'] = ta.ema(df['close'], length=200)

    # CVD (거래량·가격 변동) – 이미 있으면 그대로 사용
    if use_cvd and 'CVD' not in df.columns:
        df['CVD'] = ta.cvd(df['close'], df['volume'], length=14)

    # CVD_Signal (CVD 교차) – 이미 있으면 그대로 사용
    if use_cvd_signal and 'CVD_Signal' not in df.columns:
        df['CVD_Signal'] = ta.cvd(df['close'], df['volume'], length=14, signal=True)

    # ADX
    if use_adx and 'ADX' not in df.columns:
        df['ADX'] = ta.adx(df['high'], df['low'], df['close'], length=14)

    # RSI
    if use_rsi and 'RSI' not in df.columns:
        df['RSI'] = ta.rsi(df['close'], length=14)

    # VAL / VAH (지지·저항 레벨) – 이미 있으면 그대로 사용
    if use_val_vah and ('VAL' not in df.columns or 'VAH' not in df.columns):
        # 간단히 전일 고·저 평균을 레벨로 사용 (예시)
        df['VAL'] = df['low'].rolling(3).min()
        df['VAH'] = df['high'].rolling(3).max()

    # ------------------------------------------------------------------
    # 4️⃣ 진입 시그널 로직
    # ------------------------------------------------------------------
    # 4‑1️⃣ 구조 레벨 필터
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Above_Structure'] = df['close'] > df['VAH']

    # 4‑2️⃣ 3봉 저·고값
    df['Low_3'] = df['low'].rolling(3).min()
    df['High_3'] = df['high'].rolling(3).max()

    # 4‑3️⃣ 다이버전스 (Bull / Bear)
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    df['Bear_Div']  = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))

    # 4‑4️⃣ CVD 교차 필터
    if use_cvd_signal:
        df['CVD_Cross'] = (df['CVD'] > df['CVD_Signal']) & (df['CVD'].shift(1) <= df['CVD_Signal'].shift(1))

    # 4‑5️⃣ EMA 필터
    df['EMA'] = ta.ema(df['close'], length=ema_len)

    # 4‑6️⃣ ADX 필터 (추세 약함)
    if use_adx_filter:
        df['ADX_Weak'] = df['ADX'] <= 25

    # 4‑7️⃣ EMA_200 필터
    if use_ema_200_filter:
        df['EMA200_Weak'] = df['close'] >= df['EMA_200']

    # 4‑8️⃣ 최종 롱/숏 시그널
    # 롱
    long_cond = (
        df['Below_Structure'] &
        df['Bull_Div'] &
        (df['CVD'] > df['CVD_Signal'] if use_cvd_signal else True) &
        (df['close'] > df['EMA']) &
        ((df['ADX_Weak'] if use_adx_filter else True) |
         (df['EMA200_Weak'] if use_ema_200_filter else True))
    )
    df['Long_Signal'] = long_cond.astype(bool)

    # 숏
    short_cond = (
        df['Above_Structure'] &
        df['Bear_Div'] &
        (df['CVD'] < df['CVD_Signal'] if use_cvd_signal else True) &
        (df['close'] < df['EMA']) &
        ((df['ADX_Weak'] if use_adx_filter else True) |
         (df['EMA200_Weak'] if use_ema_200_filter else True))
    )
    df['Short_Signal'] = short_cond.astype(bool)

    # ------------------------------------------------------------------
    # 5️⃣ 현재 시점 TP / SL 반환
    # ------------------------------------------------------------------
    last_tp = df['target_tp'].iloc[-1]
    last_sl = df['target_sl'].iloc[-1]

    return df, {'tp': float(last_tp), 'sl': float(last_sl)}