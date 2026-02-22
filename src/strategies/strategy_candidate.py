import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Tuple, Dict

def apply_strategy(df: pd.DataFrame, params: Dict) -> Tuple[pd.DataFrame, Dict]:
    """
    Enhanced divergence + structure breakout strategy with dynamic filters,
    multi‑timeframe EMA confirmation, Squeeze breakout detection,
    ATR‑based trailing stop and risk‑per‑trade sizing.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame that already contains the following indicator columns:
        VAL, VAH, POC, CVD, CVD_Signal, ADX, Squeeze_On, EMA_200.
    params : dict
        Strategy configuration. Keys:
        - ema_len : int (default 30)
        - tp : float (target profit fraction, default 0.02)
        - sl : float (stop loss fraction, default 0.015)
        - max_pos : float (max position size fraction of equity, default 1.0)
        - risk_per_trade : float (risk per trade fraction of equity, default 0.01)
        - adx_min, adx_max : int (ADX trend filter bounds, default 20, 50)
        - ema_50_len, ema_20_len : int (EMA look‑back windows, default 50, 20)
        - atr_window : int (ATR look‑back, default 5)
        - squeeze_on_filter : bool (require Squeeze_On=True, default True)

    Returns
    -------
    tuple
        (df, result_params) where `df` now contains signal columns and
        `result_params` records the effective parameters.
    """
    # --------------------------------------------------------------------- defaults
    ema_len = params.get('ema_len', 30)
    tp = params.get('tp', 0.02)          # 2 % target profit
    sl = params.get('sl', 0.015)         # 1.5 % stop loss
    max_pos = params.get('max_pos', 1.0)  # full equity
    risk_per_trade = params.get('risk_per_trade', 0.01)  # 1 % risk per trade
    adx_min = params.get('adx_min', 20)
    adx_max = params.get('adx_max', 50)
    ema_50_len = params.get('ema_50_len', 50)
    ema_20_len = params.get('ema_20_len', 20)
    atr_window = params.get('atr_window', 5)
    squeeze_on_filter = params.get('squeeze_on_filter', True)

    # --------------------------------------------------------------------- sanity check
    required = {
        'VAL', 'VAH', 'POC', 'CVD', 'CVD_Signal',
        'ADX', 'Squeeze_On', 'EMA_200',
        'close', 'high', 'low', 'RSI'
    }
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing indicator columns: {missing}")

    # --------------------------------------------------------------------- 1. Dynamic support / resistance look‑back levels
    df['Low_Lookback'] = df['low'].rolling(window=atr_window).min().fillna(df['low'])
    df['High_Lookback'] = df['high'].rolling(window=atr_window).max().fillna(df['high'])

    # --------------------------------------------------------------------- 2. Divergence detection (boolean)
    df['Below_Structure'] = (df['close'] < df['VAL'] * 1.001).fillna(False).astype(bool)
    df['Above_Structure'] = (df['close'] > df['VAH'] * 0.999).fillna(False).astype(bool)

    df['Bull_Div'] = ((df['low'] <= df['Low_Lookback']) &
                      (df['RSI'] > df['RSI'].shift(1))).fillna(False).astype(bool)
    df['Bear_Div'] = ((df['high'] >= df['High_Lookback']) &
                      (df['RSI'] < df['RSI'].shift(1))).fillna(False).astype(bool)

    # --------------------------------------------------------------------- 3. CVD entry / exit
    df['CVD_Entry'] = (df['CVD'] > df['CVD_Signal']).fillna(False).astype(bool)
    df['CVD_Exit'] = (df['CVD'] < df['CVD_Signal']).fillna(False).astype(bool)

    # --------------------------------------------------------------------- 4. ADX trend filter
    df['Trend_Filter'] = ((df['ADX'] >= adx_min) & (df['ADX'] <= adx_max)).fillna(False).astype(bool)

    # --------------------------------------------------------------------- 5. Multi‑timeframe EMA confirmation
    df['EMA_50'] = ta.ema(df['close'], length=ema_50_len).rename('EMA_50')
    df['EMA_20'] = ta.ema(df['close'], length=ema_20_len).rename('EMA_20')
    df['EMA_Filter'] = ((df['EMA_50'] > df['EMA_200']) &
                        (df['EMA_20'] > df['EMA_200'])).fillna(False).astype(bool)

    # --------------------------------------------------------------------- 6. Squeeze breakout filter
    df['Squeeze_Filter'] = df['Squeeze_On'].fillna(False).astype(bool)

    # --------------------------------------------------------------------- 7. Composite entry rules
    df['Long_Entry'] = (
        df['Below_Structure'] &
        df['Bull_Div'] &
        df['CVD_Entry'] &
        df['Trend_Filter'] &
        df['EMA_Filter'] &
        df['Squeeze_Filter']
    ).astype(bool)

    df['Short_Entry'] = (
        df['Above_Structure'] &
        df['Bear_Div'] &
        df['CVD_Exit'] &
        df['Trend_Filter'] &
        df['EMA_Filter'] &
        df['Squeeze_Filter']
    ).astype(bool)

    # --------------------------------------------------------------------- 8. Signal generation (+1 / -1 / 0)
    df['Signal'] = np.where(df['Long_Entry'], 1,
                    np.where(df['Short_Entry'], -1, 0))

    # --------------------------------------------------------------------- 9. Entry price (previous close)
    df['Entry'] = df['Signal'].shift(1) * df['close']

    # --------------------------------------------------------------------- 10. Fixed SL / TP (fraction of entry)
    df['Stop'] = df['Entry'] * (1 - sl)          # hard stop‑loss level
    df['Target'] = df['Entry'] * (1 + tp)        # hard profit target level

    # --------------------------------------------------------------------- 11. ATR‑based trailing stop (optional, low‑overhead)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close']).rename('ATR')
    df['ATR_Stop'] = df['ATR'].shift(1) * (sl + 0.005)  # 0.5 % buffer above SL
    df['Trailing_Stop'] = np.where(
        df['Signal'] == 1,
        df['high'].cummax() * (1 - sl),
        df['low'].cummin() * (1 + sl)
    ).fillna(np.nan)

    # --------------------------------------------------------------------- 12. Risk‑per‑trade sizing (if equity column exists)
    if 'Equity' in df.columns:
        df['Risk_Amount'] = df['Equity'] * risk_per_trade
        df['Pos_Size'] = np.where(
            (df['Signal'] == 1) & (df['Entry'] > df['Stop']),
            df['Risk_Amount'] / (df['Entry'] - df['Stop']),
            np.where(
                (df['Signal'] == -1) & (df['Entry'] < df['Stop']),
                df['Risk_Amount'] / (df['Stop'] - df['Entry']),
                0.0
            )
        )
    else:
        df['Risk_Amount'] = np.nan
        df['Pos_Size'] = np.nan

    # --------------------------------------------------------------------- return effective params dict
    result_params = {
        'ema_len': ema_len,
        'tp': tp,
        'sl': sl,
        'max_pos': max_pos,
        'risk_per_trade': risk_per_trade,
        'adx_min': adx_min,
        'adx_max': adx_max,
        'ema_50_len': ema_50_len,
        'ema_20_len': ema_20_len,
        'atr_window': atr_window,
        'squeeze_on_filter': squeeze_on_filter,
        'added_columns': list(df.columns)   # debug helper
    }

    return df, result_params