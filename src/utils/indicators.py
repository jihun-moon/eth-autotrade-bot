import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    # 1. 기본 지표
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['EMA_200'] = ta.ema(df['close'], length=200)
    
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
    df['ADX'] = adx_df['ADX_14'] if adx_df is not None else 0

    # 2. 볼륨 프로파일 (VAL, VAH)
    lookback = 480
    if len(df) >= lookback:
        window = df.iloc[-lookback:]
        mid_prices = (window['high'] + window['low']) / 2
        vols, bin_edges = np.histogram(mid_prices, bins=50, weights=window['volume'])
        poc_idx = np.argmax(vols)
        va_target = vols.sum() * 0.7
        current_v, l, r = vols[poc_idx], poc_idx, poc_idx
        while current_v < va_target and (l > 0 or r < len(vols)-1):
            lv = vols[l-1] if l > 0 else 0
            rv = vols[r+1] if r < len(vols)-1 else 0
            if lv >= rv: current_v += lv; l -= 1
            else: current_v += rv; r += 1
        df['VAL'], df['VAH'] = bin_edges[l], bin_edges[r+1]

    # 3. CVD (Cumulative Volume Delta) - AI 전략의 핵심 재료
    df['vol_delta'] = np.where(df['close'] >= df['close'].shift(1), df['volume'], -df['volume'])
    df['CVD'] = df['vol_delta'].cumsum()
    df['CVD_Signal'] = ta.ema(df['CVD'], length=20)
    
    return df