import pandas_ta as ta
import numpy as np

def apply_strategy(df, ema_len=30, adx_thresh=20):
    """
    Apply the improved long/short signal strategy.
    - Long: price crosses up from below VAL (bounce) + bullish divergence + ADX strength + CVD condition
    - Short: price crosses down from above VAH (bounce) + bearish divergence + ADX strength + CVD condition
    - Only enter when Squeeze_On is False (no volatility explosion).
    """
    # EMA (forward‑fill NaNs)
    df['EMA_200'] = ta.ema(df['close'], length=ema_len).fillna(method='ffill')

    # Bullish divergence (lower low + higher RSI)
    df['Bull_Div'] = (
        (df['low'] < df['low'].shift(1)) &
        (df['RSI'] > df['RSI'].shift(1))
    ).astype(bool).fillna(False).astype(bool)

    # Bearish divergence (higher high + lower RSI)
    df['Bear_Div'] = (
        (df['high'] > df['high'].shift(1)) &
        (df['RSI'] < df['RSI'].shift(1))
    ).astype(bool).fillna(False).astype(bool)

    # ADX filter (strength > threshold)
    df['ADX_Filter'] = (df['ADX'] > adx_thresh).astype(bool).fillna(False).astype(bool)

    # Squeeze filter (only when not in squeeze)
    df['Squeeze_Filter'] = (df['Squeeze_On'].astype(bool) == False).astype(bool).fillna(False).astype(bool)

    # Long bounce detection: close crosses above VAL from below
    df['VAL_cross_up'] = (
        (df['close'] > df['VAL']) &
        (df['close'].shift(1) <= df['VAL'])
    ).astype(bool).fillna(False).astype(bool)

    # Short bounce detection: close crosses below VAH from above
    df['VAH_cross_down'] = (
        (df['close'] < df['VAH']) &
        (df['close'].shift(1) >= df['VAH'])
    ).astype(bool).fillna(False).astype(bool)

    # CVD condition (already present as numeric columns)
    # CVD_Signal is assumed to be a numeric threshold column

    # Long signal
    df['Long_Signal'] = (
        df['VAL_cross_up'] &
        df['Bull_Div'] &
        df['ADX_Filter'] &
        (df['CVD'] > df['CVD_Signal']) &
        (df['close'] > df['EMA_200']) &
        df['Squeeze_Filter']
    ).astype(bool).fillna(False).astype(bool)

    # Short signal
    df['Short_Signal'] = (
        df['VAH_cross_down'] &
        df['Bear_Div'] &
        df['ADX_Filter'] &
        (df['CVD'] < df['CVD_Signal']) &
        (df['close'] < df['EMA_200']) &
        df['Squeeze_Filter']
    ).astype(bool).fillna(False).astype(bool)

    return df, {'tp': 0.02, 'sl': 0.015}