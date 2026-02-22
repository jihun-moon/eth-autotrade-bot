import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    """지표 통합 계산 (Volume Profile + Squeeze Momentum)"""
    if df is None or len(df) < 200: return df
    
    # 1. 기본 지표 계산
    df['RSI'] = ta.rsi(df['close'], length=14).fillna(50)
    df['EMA_200'] = ta.ema(df['close'], length=200).fillna(df['close'])
    df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14'].fillna(0)

    # 2. 볼륨 프로파일 (Histogram 방식)
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
        df['VAL'] = df['close'].rolling(100).quantile(0.2)
        df['VAH'] = df['close'].rolling(100).quantile(0.8)

    # 3. 스퀴즈 모멘텀 (KeyError 동적 방어)
    bb = ta.bbands(df['close'], length=20, std=2.0)
    kc = ta.kc(df['high'], df['low'], df['close'], length=20, scalar=1.5)
    df = pd.concat([df, bb, kc], axis=1)
    
    try:
        bbl_col = [c for c in df.columns if c.startswith('BBL_')][0]
        bbu_col = [c for c in df.columns if c.startswith('BBU_')][0]
        kcl_col = [c for c in df.columns if c.startswith('KCL') or c.startswith('KCLe')][0]
        kcu_col = [c for c in df.columns if c.startswith('KCU') or c.startswith('KCUe')][0]
        df['Squeeze_On'] = (df[bbl_col] > df[kcl_col]) & (df[bbu_col] < df[kcu_col])
    except:
        df['Squeeze_On'] = False

    # 4. CVD (수급 지표)
    vol_delta = np.where(df['close'] > df['open'], df['volume'] * 0.6, -df['volume'] * 0.6)
    df['CVD'] = ta.ema(pd.Series(vol_delta, index=df.index), length=14)
    df['CVD_Signal'] = ta.sma(df['CVD'], length=9)

    return df.ffill().bfill()