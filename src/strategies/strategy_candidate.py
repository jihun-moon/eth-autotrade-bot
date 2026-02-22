# -*- coding: utf-8 -*-
"""
Strategy candidate implementation for cryptocurrency quantitative trading.
This module defines a function `run_strategy` that takes a DataFrame of price data,
calculates technical indicators using pandas_ta (fallback from TA‑Lib if available),
applies a simple moving‑average crossover strategy, and returns the processed DataFrame
and the parameters used.
"""

import importlib
import logging
import pandas as pd
import numpy as np

# Try to import TA‑Lib (ta) if available; otherwise use pandas_ta as a fallback.
try:
    import ta  # TA‑Lib
except ImportError:
    import pandas_ta as ta  # pandas_ta as fallback
    logging.warning("TA‑Lib not found; using pandas_ta as fallback.")

def run_strategy(df: pd.DataFrame, params: dict) -> tuple[pd.DataFrame, dict]:
    """
    Execute a simple moving‑average (SMA) crossover strategy.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame containing at least columns: 'timestamp', 'open', 'high',
        'low', 'close', 'volume'.
    params : dict
        Strategy parameters, e.g., {'fast_window': 10, 'slow_window': 30,
        'threshold': 0.001}.

    Returns
    -------
    tuple[pd.DataFrame, dict]
        - Updated DataFrame with additional columns: 'fast_sma', 'slow_sma',
          'signal', 'position', 'return'.
        - The same params dict (potentially updated with runtime statistics).
    """
    # Ensure required columns exist
    required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Work on a copy to avoid mutating the caller's DataFrame
    df = df.copy()

    # Calculate fast and slow SMAs using pandas_ta
    fast_sma = ta.sma(df['close'], length=params.get('fast_window', 10))
    slow_sma = ta.sma(df['close'], length=params.get('slow_window', 30))

    # Align SMA series to the original DataFrame index
    df['fast_sma'] = fast_sma
    df['slow_sma'] = slow_sma

    # Generate signal: 1 when fast SMA crosses above slow SMA,
    # -1 when fast SMA crosses below slow SMA, 0 otherwise
    crossover = ta.crossover(fast_sma, slow_sma)
    crossunder = ta.crossunder(fast_sma, slow_sma)

    df['signal'] = crossover.astype(int) - crossunder.astype(int)  # 1, -1, 0

    # Simple position logic: hold 1 if signal == 1, -1 if signal == -1, 0 otherwise
    df['position'] = df['signal'].replace({1: 1, -1: -1, 0: 0})

    # Optional: compute simple returns based on position
    df['return'] = df['position'].shift(1) * df['close'].pct_change()

    # Update params with runtime statistics (e.g., number of trades, win rate)
    params['trades'] = df['signal'].replace({1: 1, -1: -1, 0: 0}).sum()
    params['win_rate'] = (df['return'] > 0).sum() / df['return'].count()

    # Return the enriched DataFrame and the params dict
    return df, params


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Dummy data generation
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.random.uniform(100, 200, size=len(dates)),
        'high': np.random.uniform(100, 200, size=len(dates)),
        'low': np.random.uniform(100, 200, size=len(dates)),
        'close': np.random.uniform(100, 200, size=len(dates)),
        'volume': np.random.randint(1000, 5000, size=len(dates))
    })

    params = {
        'fast_window': 10,
        'slow_window': 30,
        'threshold': 0.001
    }

    df_out, params_out = run_strategy(df, params)
    print(df_out.head())
    print("Strategy parameters after run:", params_out)