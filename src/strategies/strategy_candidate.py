import pandas as pd
import numpy as np

def apply_strategy(df: pd.DataFrame, params_dict: dict) -> tuple[pd.DataFrame, dict]:
    """
    Improve the long/short divergence‑plus‑order‑flow strategy.

    - Uses existing indicator columns: VAL, VAH, POC, CVD, ADX, Squeeze_On.
    - Adds EMA‑200 trend filter, ADX strength filter, and volatility‑filter.
    - Enriches signals with entry price, target (TP) and stop (SL) levels.
    - Returns the enriched DataFrame and the unchanged parameter dictionary.
    """
    # ------------------------------------------------------------------
    # 1️⃣  Parameters & defaults
    # ------------------------------------------------------------------
    ema_len = params_dict.get("ema_len", 30)
    tp      = params_dict.get("tp", 0.02)      # 2 % profit target
    sl      = params_dict.get("sl", 0.015)    # 1.5 % stop loss
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 2️⃣  Long side – “VAL‑breakout + bullish divergence + trend”
    # ------------------------------------------------------------------
    #   a) Price is still inside the VAL band (just below the upper edge)
    df["Below_Structure"] = df["close"] < (df["VAL"] * 1.001)

    #   b) Bullish divergence:
    #       low of the current bar ≤ rolling minimum of the last 5 lows,
    #       RSI rises compared to the previous bar
    df["Low_Lookback"]   = df["low"].rolling(window=5).min()
    df["Bull_Div"]       = (df["low"] <= df["Low_Lookback"]) & (df["RSI"] > df["RSI"].shift(1))

    #   c) CVD crossover: CVD is above its own signal line
    df["Long_Signal"] = (
        df["Below_Structure"] &
        df["Bull_Div"] &
        (df["CVD"] > df["CVD_Signal"])
    )

    #   d) Trend & ADX strength filter
    df["Long_Signal"] = (
        df["Long_Signal"] &
        ((df["ADX"] <= 25) | (df["close"] >= df["EMA_200"]))
    )

    #   e) Volatility filter – only enter when the market is not squeezed
    df["Long_Signal"] = df["Long_Signal"] & (df["Squeeze_On"] <= 0)

    # ------------------------------------------------------------------
    # 3️⃣  Short side – “VAH‑breakout + bearish divergence + trend”
    # ------------------------------------------------------------------
    #   a) Price is still inside the VAH band (just above the lower edge)
    df["Above_Structure"] = df["close"] > (df["VAH"] * 0.999)

    #   b) Bearish divergence:
    #       high of the current bar ≥ rolling maximum of the last 5 highs,
    #       RSI falls compared to the previous bar
    df["High_Lookback"]   = df["high"].rolling(window=5).max()
    df["Bear_Div"]        = (df["high"] >= df["High_Lookback"]) & (df["RSI"] < df["RSI"].shift(1))

    #   c) CVD cross‑under: CVD is below its own signal line
    df["Short_Signal"] = (
        df["Above_Structure"] &
        df["Bear_Div"] &
        (df["CVD"] < df["CVD_Signal"])
    )

    #   d) Trend & ADX strength filter
    df["Short_Signal"] = (
        df["Short_Signal"] &
        ((df["ADX"] <= 25) | (df["close"] <= df["EMA_200"]))
    )

    #   e) Volatility filter – same as long side
    df["Short_Signal"] = df["Short_Signal"] & (df["Squeeze_On"] <= 0)

    # ------------------------------------------------------------------
    # 4️⃣  Combine signals & forward‑fill NaNs
    # ------------------------------------------------------------------
    df["Signal"] = np.where(df["Long_Signal"], 1,
                np.where(df["Short_Signal"], -1, 0))

    # ------------------------------------------------------------------
    # 5️⃣  Entry‑price & risk‑management columns (TP / SL)
    # ------------------------------------------------------------------
    #   a) Only consider the first bar where a signal appears
    df["EntryPrice"] = df["Signal"].shift(1) * df["close"]

    #   b) Target = entry × (1 + tp), Stop = entry × (1 – sl)
    df["Target"] = df["EntryPrice"] * (1 + tp)
    df["Stop"]  = df["EntryPrice"] * (1 - sl)

    #   c) Binary flags for when TP / SL are hit
    df["TP"] = (df["close"] >= df["Target"]) & (df["Signal"] == 1)
    df["SL"] = (df["close"] <= df["Stop"])  & (df["Signal"] == 1)

    #   d) Remove rows that are already closed (keep only open positions)
    df["Position"] = df["Signal"] * df["Signal"].shift(1)   # 1 → 1, -1 → -1, 0 → 0
    df["Position"] = df["Position"].fillna(0)              # fill NaNs (first bar)
    df["Open"] = df["Position"] == df["Signal"]
    df = df[df["Open"]]                                   # keep only live signals

    # ------------------------------------------------------------------
    # 6️⃣  Return enriched DataFrame + unchanged parameters
    # ------------------------------------------------------------------
    return df, params_dict