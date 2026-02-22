import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    if df is None or len(df) < 200: return df
    
    # 1. 기본 지표
    df['RSI'] = ta.rsi(df['close'], length=14).fillna(50)
    df['EMA_200'] = ta.ema(df['close'], length=200).fillna(df['close'])
    df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14'].fillna(0)

    # 2. 볼륨 프로파일 (안정화 버전 Histogram 방식)
    lookback = 480
    if len(df) >= lookback:
        window = df.iloc[-lookback:]
        mid_prices = (window['high'] + window['low']) / 2
        vols, bin_edges = np.histogram(mid_prices, bins=50, weights=window['volume'])
        poc_idx = np.argmax(vols)
        df['POC'] = (bin_edges[poc_idx] + bin_edges[poc_idx+1]) / 2
        va_target = vols.sum() * 0.7
        current_v, l, r = vols[poc_idx], poc_idx, poc_idx
        while current_v < va_target and (l > 0 or r < len(vols)-1):
            lv, rv = (vols[l-1] if l > 0 else 0), (vols[r+1] if r < len(vols)-1 else 0)
            if lv >= rv: current_v += lv; l -= 1
            else: current_v += rv; r += 1
        df['VAL'], df['VAH'] = bin_edges[l], bin_edges[r+1]
    else:
        df['VAL'], df['VAH'] = df['close'].quantile(0.2), df['close'].quantile(0.8)

    # 3. 스퀴즈 모멘텀
    bb = ta.bbands(df['close'], length=20, std=2.0)
    kc = ta.kc(df['high'], df['low'], df['close'], length=20, scalar=1.5)
    df = pd.concat([df, bb, kc], axis=1)
    try:
        bbl = [c for c in df.columns if c.startswith('BBL_')][0]
        kcl = [c for c in df.columns if c.startswith('KCL') or c.startswith('KCLe')][0]
        df['Squeeze_On'] = df[bbl] > df[kcl]
    except: df['Squeeze_On'] = False

    # 4. 수급(CVD)
    vol_delta = np.where(df['close'] > df['open'], df['volume'] * 0.6, -df['volume'] * 0.6)
    df['CVD'] = ta.ema(pd.Series(vol_delta, index=df.index), length=14)
    df['CVD_Signal'] = ta.sma(df['CVD'], length=9)
    return df.ffill().bfill()