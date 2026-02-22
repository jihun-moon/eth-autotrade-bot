import pandas_ta as ta
import numpy as np

def apply_strategy(df, ema_len: int = 30) -> tuple[pd.DataFrame, dict]:
    """
    ATR 기반 TP/SL 를 계산하고, CVD·ADX·EMA_200·VAL·VAH 를 활용한 롱·숏 진입 시그널을 생성합니다.
    
    Parameters
    ----------
    df : pd.DataFrame
        OHLCV 컬럼이 포함된 원본 데이터프레임.
        반드시 아래 컬럼이 존재해야 합니다.
        - high, low, close
        - CVD, CVD_Signal
        - ADX
        - EMA_200
        - VAL, VAH
        - RSI (전략 내부에서 사용)
    
    ema_len : int, optional
        EMA(20) 길이 (기본값 30). 롱·숏 진입 시 EMA 교차 판단에 사용됩니다.
    
    Returns
    -------
    tuple
        (전략 적용 후 DataFrame, {'tp': 마지막 TP 비율, 'sl': 마지막 SL 비율})
    """
    # -------------------------------------------------
    # 1️⃣ ATR 기반 TP / SL 비율 컬럼 생성
    # -------------------------------------------------
    df["ATR"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    # TP = ATR × 2 / 현재 종가 → 최소 1.5% 로 제한
    tp_ratio = (df["ATR"] * 2.0 / df["close"]).fillna(0.02)   # NaN → 2%
    df["target_tp"] = np.clip(tp_ratio, a_min=0.015, a_max=None)

    # SL = ATR × 1.5 / 현재 종가 → 최소 1% 로 제한
    sl_ratio = (df["ATR"] * 1.5 / df["close"]).fillna(0.015)  # NaN → 1.5%
    df["target_sl"] = np.clip(sl_ratio, a_min=0.01, a_max=None)

    # -------------------------------------------------
    # 2️⃣ 시그널 로직 (CVD, 매물대, EMA 결합)
    # -------------------------------------------------
    # RSI 컬럼이 없으면 에러 발생 → 사전에 계산돼 있다고 가정
    # (필요 시 아래처럼 직접 계산 가능)
    # df["RSI"] = ta.rsi(df["close"], length=14)

    # 롱 진입 조건
    df["Below_Structure"] = df["close"] < df["VAL"]
    df["Low_3"] = df["low"].rolling(3).min()
    df["Bull_Div"] = (df["low"] == df["Low_3"]) & (df["RSI"] > df["RSI"].shift(1))

    df["Long_Signal"] = (
        df["Below_Structure"] &
        df["Bull_Div"] &
        (df["CVD"] > df["CVD_Signal"]) &
        (df["close"] > ta.ema(df["close"], length=ema_len))
    ) & (
        (df["ADX"] <= 25) | (df["close"] >= df["EMA_200"])
    )

    # 숏 진입 조건
    df["Above_Structure"] = df["close"] > df["VAH"]
    df["High_3"] = df["high"].rolling(3).max()
    df["Bear_Div"] = (df["high"] == df["High_3"]) & (df["RSI"] < df["RSI"].shift(1))

    df["Short_Signal"] = (
        df["Above_Structure"] &
        df["Bear_Div"] &
        (df["CVD"] < df["CVD_Signal"]) &
        (df["close"] < ta.ema(df["close"], length=ema_len))
    ) & (
        (df["ADX"] <= 25) | (df["close"] <= df["EMA_200"])
    )

    # -------------------------------------------------
    # 3️⃣ 실전(Live)용 현재 시점 파라미터 반환
    # -------------------------------------------------
    # TP/SL 컬럼이 반드시 존재해야 함 → 검증
    if "target_tp" not in df.columns or "target_sl" not in df.columns:
        raise KeyError("전략 결과 데이터프레임에 'target_tp'와 'target_sl' 컬럼이 반드시 포함되어야 합니다.")

    last_tp = df["target_tp"].iloc[-1]
    last_sl = df["target_sl"].iloc[-1]

    return df, {"tp": last_tp, "sl": last_sl}