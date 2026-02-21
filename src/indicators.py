import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    # 1. 기본 지표 계산
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    
    # 2. 볼륨 프로파일 계산 (최근 480캔들 기준 매물대 확인)
    lookback = 480
    if len(df) >= lookback:
        window = df.iloc[-lookback:]
        bins = np.linspace(window['low'].min(), window['high'].max(), 50)
        vols = np.zeros(len(bins)-1)
        for _, row in window.iterrows():
            idx = np.digitize((row['high'] + row['low']) / 2, bins) - 1
            if 0 <= idx < len(vols): vols[idx] += row['volume']
        
        poc_idx = np.argmax(vols)
        df['POC'] = (bins[poc_idx] + bins[poc_idx+1]) / 2  # 회색선 (Point of Control)
        
        # 가치 영역(VA 70%) 계산
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
        df['VAL'] = bins[l]  # 파란영역 하단 (Value Area Low)
        df['VAH'] = bins[r]  # 파란영역 상단 (Value Area High)
    
    # 3. 스퀴즈 모멘텀 (안전한 컬럼 참조 방식)
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