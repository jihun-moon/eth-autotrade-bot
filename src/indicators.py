import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    """Pine Script v16.1 로직을 파이썬으로 완벽 이식"""
    # 1. 기본 RSI 및 EMA
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    
    # 2. Squeeze Momentum (BB vs KC)
    bb = ta.bbands(df['close'], length=20, std=2.0)
    kc = ta.kc(df['close'], length=20, scalar=1.5)
    df['Squeeze_On'] = (bb['BBL_20_2.0'] > kc['KCL_20_1.5']) & (bb['BBU_20_2.0'] < kc['KCU_20_1.5'])

    # 3. CVD (Cumulative Volume Delta) - Pine Script 수식 이식
    spread = (df['high'] - df['low']).replace(0, 0.001)
    upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
    lower_wick = df[['open', 'close']].min(axis=1) - df['low']
    body_length = (df['open'] - df['close']).abs()
    
    pct_wick_avg = ((upper_wick / spread) + (lower_wick / spread)) / 2
    pct_body = body_length / spread
    
    is_bull = df['close'] > df['open']
    buying_vol = np.where(is_bull, (pct_body + pct_wick_avg) * df['volume'], pct_wick_avg * df['volume'])
    selling_vol = np.where(~is_bull, (pct_body + pct_wick_avg) * df['volume'], pct_wick_avg * df['volume'])
    
    df['CVD'] = ta.ema(pd.Series(buying_vol - selling_vol, index=df.index), length=14)
    df['CVD_Signal'] = ta.sma(df['CVD'], length=9)
    
    # 4. Killzones (KST 기준 세팅)
    # Pine Script: Asia(20:00-00:00 EST) -> 한국시간 약 09:00-13:00
    hour = df.index.hour
    df['is_asia'] = (hour >= 9) & (hour < 13)
    df['is_london'] = (hour >= 16) & (hour < 20)
    df['is_ny_am'] = (hour >= 22) | (hour < 1)
    df['is_killzone'] = df['is_asia'] | df['is_london'] | df['is_ny_am']

    return df.dropna()