import pandas_ta as ta
import numpy as np

def apply_strategy(df, ema_len=30):
    # Ensure ADX and EMA_200 are present (compute if missing)
    if 'ADX' not in df.columns:
        df['ADX'] = ta.adx(df['high'], df['low'], df['close'], length=14)
    if 'EMA_200' not in df.columns:
        df['EMA_200'] = ta.ema(df['close'], length=200)

    # ---------- Long entry ----------
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))

    df['Long_Signal'] = (
        df['Below_Structure'] &
        df['Bull_Div'] &
        (df['CVD'] > df['CVD_Signal']) &
        (df['close'] > ta.ema(df['close'], length=ema_len))
    )

    # Block long entry when strong downtrend (ADX > 25 & close < EMA_200)
    df['Long_Signal'] = df['Long_Signal'] & (
        (df['ADX'] <= 25) | (df['close'] >= df['EMA_200'])
    )

    # ---------- Short entry ----------
    df['Above_Structure'] = df['close'] > df['VAH']
    df['High_3'] = df['high'].rolling(3).max()
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))

    df['Short_Signal'] = (
        df['Above_Structure'] &
        df['Bear_Div'] &
        (df['CVD'] < df['CVD_Signal']) &
        (df['close'] < ta.ema(df['close'], length=ema_len))
    )

    # Block short entry when strong uptrend (ADX > 25 & close > EMA_200)
    df['Short_Signal'] = df['Short_Signal'] & (
        (df['ADX'] <= 25) | (df['close'] <= df['EMA_200'])
    )

    # ---------- Additional risk flags ----------
    df['Strong_Uptrend'] = (df['ADX'] > 25) & (df['close'] > df['EMA_200'])
    df['Strong_Downtrend'] = (df['ADX'] > 25) & (df['close'] < df['EMA_200'])

    # Apply risk filter: discard opposite signals in strong trends
    df['Long_Signal'] = df['Long_Signal'] & ~df['Strong_Downtrend']
    df['Short_Signal'] = df['Short_Signal'] & ~df['Strong_Uptrend']

    # Optional: risk indicator column (0 = safe, 1 = risky)
    df['Signal_Risk'] = np.where(df['Long_Signal'] | df['Short_Signal'], 0, 1)

    return df