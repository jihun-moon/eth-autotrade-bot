import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    """예전 안정화 버전의 Volume Profile + Squeeze Momentum 통합"""
    if df is None or len(df) < 200: return df
    
    # 1. 기본 지표
    df['RSI'] = ta.rsi(df['close'], length=14).fillna(50)
    df['EMA_200'] = ta.ema(df['close'], length=200).fillna(df['close'])
    df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14'].fillna(0)

    # 2. 정교한 볼륨 프로파일 (보내주신 Histogram 방식 적용)
    lookback = 480
    if len(df) >= lookback:
        window = df.tail(lookback)
        vols, bin_edges = np.histogram(window['close'], bins=50, weights=window['volume'])
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

    # 3. 스퀴즈 모멘텀 (보내주신 로직 추가)
    bb = ta.bbands(df['close'], length=20, std=2.0)
    kc = ta.kc(df['high'], df['low'], df['close'], length=20, scalar=1.5)
    if bb is not None and kc is not None:
        df['Squeeze_On'] = (bb['BBL_20_2.0'] > kc['LKC_20_1.5']) & (bb['BBU_20_2.0'] < kc['UKC_20_1.5'])
    
    # 4. CVD (수급 지표)
    df['vol_delta'] = np.where(df['close'] >= df['close'].shift(1), df['volume'], -df['volume'])
    df['CVD'] = df['vol_delta'].cumsum()
    df['CVD_Signal'] = ta.ema(df['CVD'], length=20).fillna(df['CVD'])
    
    return df.ffill().bfill()