import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30):
    """
    Improved SMC + CVD + trend filter strategy.
    - Uses ADX and EMA_200 slope to block reverse entries in strong trends.
    - Adds CVD momentum filter (10‑bar rolling mean) and price volatility filter.
    - Returns df with entry/exit columns and fixed TP/SL dict.
    """
    # Ensure required columns exist
    required = ['close', 'VAL', 'VAH', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Fixed TP/SL
    df['target_tp'] = 0.02   # 2% 익절
    df['target_sl'] = 0.015  # 1.5% 손절

    # Trend strength and direction
    df['strong_trend'] = df['ADX'] > 25
    df['ema_dir'] = np.sign(df['EMA_200'].diff())  # 1 = uptrend, -1 = downtrend, 0 = flat

    # CVD momentum filter (10‑bar rolling mean)
    df['CVD_ma'] = df['CVD'].rolling(window=10, min_periods=1).mean()

    # Price volatility filter (20‑bar std)
    df['price_std'] = df['close'].rolling(window=20, min_periods=1).std()

    # ---------- LONG ENTRY ----------
    long_price_cond = df['close'] < df['VAL']
    long_cvd_cond = df['CVD'] > df['CVD_ma']
    long_cvd_sign_cond = df['CVD'] > df['CVD_Signal']
    long_vol_cond = df['close'] < df['VAH'] - 0.5 * df['price_std']
    long_filter = ~(df['strong_trend'] & (df['ema_dir'] == -1))

    df['Long_Signal'] = long_price_cond & long_cvd_cond & long_cvd_sign_cond & long_vol_cond & long_filter

    # ---------- SHORT ENTRY ----------
    short_price_cond = df['close'] > df['VAH']
    short_cvd_cond = df['CVD'] < df['CVD_ma']
    short_cvd_sign_cond = df['CVD'] < df['CVD_Signal']
    short_vol_cond = df['close'] > df['VAL'] + 0.5 * df['price_std']
    short_filter = ~(df['strong_trend'] & (df['ema_dir'] == 1))

    df['Short_Signal'] = short_price_cond & short_cvd_cond & short_cvd_sign_cond & short_vol_cond & short_filter

    # Signal column (1 = long, -1 = short, 0 = no signal)
    df['Signal'] = np.where(df['Long_Signal'], 1,
                            np.where(df['Short_Signal'], -1, 0))

    # Position column (maintains current position)
    df['Position'] = df['Signal'].shift(1).fillna(0)

    # Entry price (filled forward when position changes)
    df['Entry_Price'] = np.nan
    df['Entry_Price'] = np.where(df['Position'] != df['Signal'],
                                df['close'],
                                df['Entry_Price'].shift(1))

    # TP / SL levels (filled forward after entry)
    df['TP'] = df['Entry_Price'].fillna(method='ffill') * (1 + df['target_tp'])
    df['SL'] = df['Entry_Price'].fillna(method='ffill') * (1 - df['target_sl'])

    # Exit flags
    df['Exit_TP'] = (df['close'] >= df['TP']) & (df['Position'] == 1)
    df['Exit_SL'] = (df['close'] <= df['SL']) & (df['Position'] == -1)

    # Optional: drop intermediate helper columns if desired
    # df.drop(columns=['strong_trend','ema_dir','CVD_ma','price_std'], inplace=True)

    return df, {'tp': 0.02, 'sl': 0.015}