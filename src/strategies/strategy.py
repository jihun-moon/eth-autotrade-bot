import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30):
    """
    Improved SMC + CVD + trend filter strategy.
    - Core: VAL/VAH sweep and CVD supply‑demand reversal.
    - Trend defense: block short entries when ADX > 25 and price > EMA_200.
    - Returns df with boolean entry/exit signals and fixed TP/SL dict.
    """
    # Required columns
    required = ['close', 'VAL', 'VAH', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Fixed TP/SL (decimal fractions)
    target_tp = 0.02   # 2% profit target
    target_sl = 0.015 # 1.5% stop loss

    # Compute EMA_200 if not present
    if 'EMA_200' not in df.columns:
        df['EMA_200'] = df['close'].ta.ema(200)

    # Compute ADX if not present
    if 'ADX' not in df.columns:
        df['ADX'] = df['close'].ta.adx(14)

    # Compute CVD smoothed signal (10‑bar SMA)
    if 'CVD_Signal' not in df.columns:
        df['CVD_Signal'] = df['CVD'].ta.sma(10)

    # Compute 10‑bar rolling mean of CVD for momentum filter
    if 'CVD_ma' not in df.columns:
        df['CVD_ma'] = df['CVD'].rolling(window=10, min_periods=1).mean()

    # Trend defense: block short entries when ADX > 25 and price > EMA_200
    short_filter = ~( (df['ADX'] > 25) & (df['close'] > df['EMA_200']) )

    # ---------- LONG ENTRY ----------
    long_price_cond = df['close'] < df['VAL']
    long_cvd_cond = df['CVD'] > df['CVD_ma']
    long_cvd_sign_cond = df['CVD'] > df['CVD_Signal']
    long_signal = long_price_cond & long_cvd_cond & long_cvd_sign_cond

    # ---------- SHORT ENTRY ----------
    short_price_cond = df['close'] > df['VAH']
    short_cvd_cond = df['CVD'] < df['CVD_ma']
    short_cvd_sign_cond = df['CVD'] < df['CVD_Signal']
    short_signal = short_price_cond & short_cvd_cond & short_cvd_sign_cond & short_filter

    # Entry signals as boolean series
    df['Long_Signal'] = long_signal.astype(bool)
    df['Short_Signal'] = short_signal.astype(bool)

    # Numeric signal (1 = long, -1 = short, 0 = none)
    df['Signal'] = np.where(df['Long_Signal'], 1,
                            np.where(df['Short_Signal'], -1, 0))

    # Position (maintains current position)
    df['Position'] = df['Signal'].shift(1).fillna(0)

    # Entry price (filled forward when position changes)
    df['Entry_Price'] = np.nan
    df['Entry_Price'] = np.where(df['Position'] != df['Signal'],
                                df['close'],
                                df['Entry_Price'].shift(1))

    # TP / SL levels (filled forward after entry)
    df['TP'] = df['Entry_Price'].fillna(method='ffill') * (1 + target_tp)
    df['SL'] = df['Entry_Price'].fillna(method='ffill') * (1 - target_sl)

    # Exit flags (boolean series)
    df['Exit_TP'] = (df['close'] >= df['TP']) & (df['Position'] == 1)
    df['Exit_SL'] = (df['close'] <= df['SL']) & (df['Position'] == -1)

    # Optional: drop intermediate helper columns
    # df.drop(columns=['CVD_ma', 'CVD_Signal', 'ADX', 'EMA_200'], inplace=True)

    return df, {'tp': target_tp, 'sl': target_sl}