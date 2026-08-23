import numpy as np

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    """
    Improved SMC + CVD + trend filter strategy.
    - Core: VAL/VAH bounce entry.
    - Supply‑demand filter: CVD cross with CVD_Signal.
    - Trend defense: block entries when ADX > 25 and price deviates > 2% from EMA_200.
    Returns df with entry/exit signals and params dict.
    """
    # Required columns
    required = ['VAL', 'VAH', 'POC', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # ---------- VAL bounce detection ----------
    df['VAL_cross_down'] = (df['close'] < df['VAL']) & (df['close'].shift(1) >= df['VAL'])
    df['VAL_cross_up']   = (df['close'] > df['VAL']) & (df['close'].shift(1) <= df['VAL'])
    df['VAL_bounce']     = df['VAL_cross_up'] & df['VAL_cross_down'].shift(1)

    # ---------- VAH bounce detection ----------
    df['VAH_cross_up']   = (df['close'] > df['VAH']) & (df['close'].shift(1) <= df['VAH'])
    df['VAH_cross_down'] = (df['close'] < df['VAH']) & (df['close'].shift(1) >= df['VAH'])
    df['VAH_bounce']     = df['VAH_cross_down'] & df['VAH_cross_up'].shift(1)

    # ---------- CVD cross detection ----------
    df['CVD_cross_up']   = (df['CVD'] > df['CVD_Signal']) & (df['CVD'].shift(1) <= df['CVD_Signal'])
    df['CVD_cross_down'] = (df['CVD'] < df['CVD_Signal']) & (df['CVD'].shift(1) >= df['CVD_Signal'])

    # ---------- Trend defense ----------
    df['ADX_trend'] = df['ADX'] > 25
    df['price_dist'] = np.abs(df['close'] - df['EMA_200']) / df['EMA_200']
    df['trend_defense'] = ~(df['ADX_trend'] & (df['price_dist'] > 0.02))

    # ---------- Entry signals ----------
    long_entry = df['VAL_bounce'] & df['CVD_cross_up'] & df['trend_defense']
    short_entry = df['VAH_bounce'] & df['CVD_cross_down'] & df['trend_defense']

    df['Signal'] = np.where(long_entry, 1,
                            np.where(short_entry, -1, 0))

    # ---------- Position ----------
    df['Position'] = df['Signal'].shift(1).fillna(0)

    # ---------- Entry flag (only when exiting zero position) ----------
    df['Entry_Flag'] = (df['Signal'] != 0) & (df['Position'] == 0)

    # ---------- Entry price ----------
    df['Entry_Price'] = np.nan
    df['Entry_Price'] = np.where(df['Entry_Flag'], df['close'], df['Entry_Price'].shift(1))

    # ---------- TP / SL ----------
    df['TP'] = np.nan
    df['SL'] = np.nan
    df['TP'] = np.where(df['Entry_Flag'], df['Entry_Price'] * (1 + tp), df['TP'].shift(1))
    df['SL'] = np.where(df['Entry_Flag'], df['Entry_Price'] * (1 - sl), df['SL'].shift(1))

    # ---------- Exit flags ----------
    df['Exit_TP'] = (df['close'] >= df['TP']) & (df['Position'] == 1)
    df['Exit_SL'] = (df['close'] <= df['SL']) & (df['Position'] == -1)

    params = {'tp': tp, 'sl': sl}
    return df, params