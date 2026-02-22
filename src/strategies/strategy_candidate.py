import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df: pd.DataFrame, params_dict: dict = None):
    """
    Enhanced divergence + structure breakout strategy with multiple filters.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data that must contain (at minimum) the following columns:
            - close, high, low, volume
            - VAL, VAH, POC
            - CVD, CVD_Signal
            - ADX, Squeeze_On
            - RSI (computed by pandas_ta)
        Additional columns such as EMA_200, MACD, etc. will be computed on‑the‑fly
        if they are missing.
    params_dict : dict, optional
        Strategy parameters. If omitted, sensible defaults are applied.
        Keys and default values:
            ema_len, tp, sl,
            rsi_len, adx_len, atr_len, atr_mult,
            volume_filter,
            macd_fast, macd_slow, macd_sig,
            use_squeeze, trend_filter_len, trend_filter_direction,
            high_filter_len, low_filter_len,
            confirm_rsi_thresh, confirm_adx_thresh, confirm_vol_thresh

    Returns
    -------
    tuple
        (df_with_signal, params_used)
        df_with_signal contains all original columns plus the newly added signal columns.
    """
    # ------------------------------------------------------------------
    # 1. Parameter handling & defaults
    # ------------------------------------------------------------------
    defaults = {
        "ema_len": 30,
        "tp": 0.02,          # profit‑target multiplier (e.g., 2 %)
        "sl": 0.015,         # stop‑loss multiplier (e.g., 1.5 %)
        "rsi_len": 14,
        "adx_len": 14,
        "atr_len": 14,
        "atr_mult": 2,
        "volume_filter": 1.0,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_sig": 9,
        "use_squeeze": True,
        "trend_filter_len": 200,
        "trend_filter_direction": "up",
        "high_filter_len": 5,
        "low_filter_len": 5,
        "confirm_rsi_thresh": 50,
        "confirm_adx_thresh": 20,
        "confirm_vol_thresh": 1.0,
    }
    params = {**defaults, **(params_dict or {})}
    ema_len = params["ema_len"]
    tp = params["tp"]
    sl = params["sl"]
    rsi_len = params["rsi_len"]
    adx_len = params["adx_len"]
    atr_len = params["atr_len"]
    atr_mult = params["atr_mult"]
    volume_filter = params["volume_filter"]
    macd_fast = params["macd_fast"]
    macd_slow = params["macd_slow"]
    macd_sig = params["macd_sig"]
    use_squeeze = params["use_squeeze"]
    trend_filter_len = params["trend_filter_len"]
    trend_filter_direction = params["trend_filter_direction"]
    high_filter_len = params["high_filter_len"]
    low_filter_len = params["low_filter_len"]
    confirm_rsi_thresh = params["confirm_rsi_thresh"]
    confirm_adx_thresh = params["confirm_adx_thresh"]
    confirm_vol_thresh = params["confirm_vol_thresh"]

    # ------------------------------------------------------------------
    # 2. Required column validation
    # ------------------------------------------------------------------
    required = [
        "close", "high", "low", "volume",
        "VAL", "VAH", "POC",
        "CVD", "CVD_Signal",
        "ADX", "Squeeze_On",
        "RSI"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # ------------------------------------------------------------------
    # 3. Dynamic lookback levels
    # ------------------------------------------------------------------
    df["Low_Lookback"] = df["low"].rolling(window=low_filter_len).min()
    df["High_Lookback"] = df["high"].rolling(window=high_filter_len).max()

    # ------------------------------------------------------------------
    # 4. Trend filter – EMA_200 (optional EMA_50 for higher‑timeframe confirmation)
    # ------------------------------------------------------------------
    if "EMA_200" not in df.columns:
        df["EMA_200"] = ta.ema(df["close"], length=trend_filter_len)

    if "EMA_50" not in df.columns:
        df["EMA_50"] = ta.ema(df["close"], length=50)

    # ------------------------------------------------------------------
    # 5. MACD components (bullish / bearish cross detection)
    # ------------------------------------------------------------------
    if "MACD" not in df.columns:
        df["MACD"], df["MACD_Signal"], df["MACD_Hist"] = ta.macd(
            df["close"],
            fast=macd_fast,
            slow=macd_slow,
            signal=macd_sig,
        )
    if "MACD_Signal" not in df.columns:
        raise KeyError("Column 'MACD_Signal' is required for MACD cross detection.")

    df["MACD_Bull_Cross"] = (df["MACD"] > df["MACD_Signal"]) & (
        df["MACD"].shift(1) <= df["MACD_Signal"].shift(1)
    )
    df["MACD_Bear_Cross"] = (df["MACD"] < df["MACD_Signal"]) & (
        df["MACD"].shift(1) >= df["MACD_Signal"].shift(1)
    )

    # ------------------------------------------------------------------
    # 6. ADX (trend‑strength) filter
    # ------------------------------------------------------------------
    if "ADX" not in df.columns:
        df["ADX"] = ta.adx(df["high"], df["low"], df["close"], length=adx_len)
    df["ADX_OK"] = df["ADX"] > confirm_adx_thresh

    # ------------------------------------------------------------------
    # 7. RSI threshold filter
    # ------------------------------------------------------------------
    df["RSI_OK_Long"] = df["RSI"] > confirm_rsi_thresh
    df["RSI_OK_Short"] = df["RSI"] < confirm_rsi_thresh

    # ------------------------------------------------------------------
    # 8. Volume filter (relative to 20‑period average)
    # ------------------------------------------------------------------
    avg_vol = df["volume"].rolling(window=20).mean()
    df["Vol_Filter"] = avg_vol * volume_filter
    df["Volume_OK"] = df["volume"] >= df["Vol_Filter"]

    # ------------------------------------------------------------------
    # 9. Squeeze filter (if enabled)
    # ------------------------------------------------------------------
    if use_squeeze and "Squeeze_On" not in df.columns:
        df["Squeeze_On"] = ta.squeeze(df["high"], df["low"], df["close"])
    if "Squeeze_On" not in df.columns:
        raise KeyError("Column 'Squeeze_On' is required for the strategy.")

    # ------------------------------------------------------------------
    # 10. Price‑structure breakout filter
    # ------------------------------------------------------------------
    df["Below_Structure"] = df["close"] < (df["VAL"] * 1.001)
    df["Above_Structure"] = df["close"] > (df["VAH"] * 0.999)

    # ------------------------------------------------------------------
    # 11. Divergence detection
    # ------------------------------------------------------------------
    df["Bull_Div"] = (df["low"] <= df["Low_Lookback"]) & (df["RSI"] > df["RSI"].shift(1))
    df["Bear_Div"] = (df["high"] >= df["High_Lookback"]) & (df["RSI"] < df["RSI"].shift(1))

    # ------------------------------------------------------------------
    # 12. Trend filter based on EMA_200 (or EMA_50) direction
    # ------------------------------------------------------------------
    if trend_filter_direction == "up":
        df["Trend_OK"] = df["close"] >= df["EMA_200"]
    elif trend_filter_direction == "down":
        df["Trend_OK"] = df["close"] <= df["EMA_200"]
    else:
        df["Trend_OK"] = True  # fallback

    # ------------------------------------------------------------------
    # 13. Combine primary long and short conditions
    # ------------------------------------------------------------------
    long_cond = (
        df["Below_Structure"]
        & df["Bull_Div"]
        & df["CVD"] > df["CVD_Signal"]
        & df["Trend_OK"]
        & df["MACD_Bull_Cross"]
        & df["ADX_OK"]
        & df["RSI_OK_Long"]
        & df["Volume_OK"]
        & (df["Squeeze_On"] == False if use_squeeze else True)
    )
    df["Long_Signal"] = long_cond

    short_cond = (
        df["Above_Structure"]
        & df["Bear_Div"]
        & df["CVD"] < df["CVD_Signal"]
        & df["Trend_OK"]
        & df["MACD_Bear_Cross"]
        & df["ADX_OK"]
        & df["RSI_OK_Short"]
        & df["Volume_OK"]
        & (df["Squeeze_On"] == False if use_squeeze else True)
    )
    df["Short_Signal"] = short_cond

    # ------------------------------------------------------------------
    # 14. Assign unified signal (1 = long, -1 = short, 0 = neutral)
    # ------------------------------------------------------------------
    df["Signal"] = np.where(df["Long_Signal"], 1,
                            np.where(df["Short_Signal"], -1, 0))

    # ------------------------------------------------------------------
    # 15. Volatility‑based stop & target levels (ATR‑scaled)
    # ------------------------------------------------------------------
    if "ATR" not in df.columns:
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], length=atr_len)

    df["Long_Stop"] = df["EMA_200"] - df["ATR"] * atr_mult * sl
    df["Short_Stop"] = df["EMA_200"] + df["ATR"] * atr_mult * sl

    df["Long_TP"] = df["EMA_200"] + df["ATR"] * atr_mult * tp
    df["Short_TP"] = df["EMA_200"] - df["ATR"] * atr_mult * tp

    # ------------------------------------------------------------------
    # 16. Adjust signal when stop or profit target is hit
    # ------------------------------------------------------------------
    df["Signal"] = np.where(df["close"] <= df["Long_Stop"], 0, df["Signal"])
    df["Signal"] = np.where(df["close"] >= df["Long_TP"], 0, df["Signal"])
    df["Signal"] = np.where(df["close"] >= df["Short_TP"], 0, df["Signal"])
    df["Signal"] = np.where(df["close"] >= df["Short_Stop"], 0, df["Signal"])

    # ------------------------------------------------------------------
    # 17. Return enriched dataframe + used parameters
    # ------------------------------------------------------------------
    return df, params