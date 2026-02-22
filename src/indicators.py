import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    # 1. 기본 지표 계산
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    
    # 🔥 [추가됨] AI가 장세(Regime)를 판독할 수 있도록 지표 추가
    df['EMA_200'] = ta.ema(df['close'], length=200)
    
    # ADX 계산 (추세 강도)
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
    if adx_df is not None:
        df['ADX'] = adx_df['ADX_14'] 
    else:
        df['ADX'] = 0

    # 2. 볼륨 프로파일 계산 (최근 480캔들 기준)
    lookback = 480
    if len(df) >= lookback:
        window = df.iloc[-lookback:]
        
        mid_prices = (window['high'] + window['low']) / 2
        vols, bin_edges = np.histogram(mid_prices, bins=50, weights=window['volume'])
        
        poc_idx = np.argmax(vols)
        df['POC'] = (bin_edges[poc_idx] + bin_edges[poc_idx+1]) / 2  
        
        va_target = vols.sum() * 0.7
        current_v = vols[poc_idx]
        l, r = poc_idx, poc_idx
        while current_v < va_target and (l > 0 or r < len(vols)-1):
            lv = vols[l-1] if l > 0 else 0
            rv = vols[r+1] if r < len(vols)-1 else 0
            if lv >= rv:
                current_v += lv
                l -= 1
            else:
                current_v += rv
                r += 1
        df['VAL'] = bin_edges[l]      
        df['VAH'] = bin_edges[r+1]    
    
    # 3. 스퀴즈 모멘텀
    bb = ta.bbands(df['close'], length=20, std=2.0)
    kc = ta.kc(df['high'], df['low'], df['close'], length=20, scalar=1.5)
    df = pd.concat([df, bb, kc], axis=1)
    
    try:
        bbl_col = [c for c in df.columns if c.startswith('BBL_')][0]
        kcl_col = [c for c in df.columns if c.startswith('KCL')][0]
        df['Squeeze_On'] = df[bbl_col] > df[kcl_col]
    except:
        df['Squeeze_On'] = False

    # 4. CVD (세력 수급 확인)
    vol_delta = np.where(df['close'] > df['open'], df['volume'] * 0.6, -df['volume'] * 0.6)
    df['CVD'] = ta.ema(pd.Series(vol_delta, index=df.index), length=14)
    df['CVD_Signal'] = ta.sma(df['CVD'], length=9)

    return df.dropna()