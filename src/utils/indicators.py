import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    """모든 기술적 지표 계산 및 초기화"""
    if df is None or len(df) < 10: 
        return df
    
    # 0. 모든 필수 컬럼 초기화 (KeyError 방지)
    df['VAL'] = df['close'].rolling(100).min()
    df['VAH'] = df['close'].rolling(100).max()
    df['POC'] = df['close']
    df['CVD'] = 0.0
    df['CVD_Signal'] = 0.0
    df['ADX'] = 0.0
    df['RSI'] = 50.0

    # 1. 기본 지표 계산
    df['RSI'] = ta.rsi(df['close'], length=14).fillna(50)
    df['EMA_200'] = ta.ema(df['close'], length=200).fillna(df['close'])
    
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
    if adx_df is not None and not adx_df.empty:
        df['ADX'] = adx_df['ADX_14'].fillna(0)

    # 2. 볼륨 프로파일 (데이터가 충분할 때만 업데이트)
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
            if lv >= rv: 
                current_v += lv
                l -= 1
            else: 
                current_v += rv
                r += 1
                
        # 최신 VAL, VAH 값 적용 및 전파
        df.loc[df.index[-1], 'VAL'] = bin_edges[l]
        df.loc[df.index[-1], 'VAH'] = bin_edges[r+1]
        df['VAL'] = df['VAL'].ffill().bfill()
        df['VAH'] = df['VAH'].ffill().bfill()

    # 3. CVD (수급 지표) 추가
    df['vol_delta'] = np.where(df['close'] >= df['close'].shift(1), df['volume'], -df['volume'])
    df['CVD'] = df['vol_delta'].cumsum()
    df['CVD_Signal'] = ta.ema(df['CVD'], length=20).fillna(df['CVD'])
    
    return df