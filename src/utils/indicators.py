import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    if df is None or len(df) < 200: return df
    
    # 1. 기본 지표
    df['RSI'] = ta.rsi(df['close'], length=14).fillna(50)
    df['EMA_200'] = ta.ema(df['close'], length=200).fillna(df['close'])
    df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14'].fillna(0)

    # 2. 볼륨 프로파일 (트레이딩뷰 정밀 이식 버전)
    lookback, bins = 480, 100 # 24시간 분석, 100 해상도
    if len(df) >= lookback:
        window = df.iloc[-lookback:].copy()
        high_max, low_min = window['high'].max(), window['low'].min()
        price_interval = (high_max - low_min) / (bins - 1)
        if price_interval == 0: price_interval = 0.01
        
        vols = np.zeros(bins)
        for _, row in window.iterrows():
            # 🌟 캔들의 범위를 모두 반영하여 거래량 분배
            s_bin = int((row['low'] - low_min) / price_interval)
            e_bin = int((row['high'] - low_min) / price_interval)
            for j in range(max(0, s_bin), min(bins, e_bin + 1)):
                vols[j] += row['volume']

        poc_idx = np.argmax(vols)
        df['POC'] = low_min + (poc_idx * price_interval)
        va_target = vols.sum() * 0.7
        current_v, l, r = vols[poc_idx], poc_idx, poc_idx
        while current_v < va_target and (l > 0 or r < bins - 1):
            lv, rv = (vols[l-1] if l > 0 else 0), (vols[r+1] if r < bins - 1 else 0)
            if lv >= rv: current_v += lv; l -= 1
            else: current_v += rv; r += 1
        df['VAL'], df['VAH'] = low_min + (l * price_interval), low_min + (r * price_interval)
    else:
        df['VAL'], df['VAH'], df['POC'] = df['close'].quantile(0.2), df['close'].quantile(0.8), df['close'].median()

    # 3. 스퀴즈 모멘텀
    bb = ta.bbands(df['close'], length=20, std=2.0)
    kc = ta.kc(df['high'], df['low'], df['close'], length=20, scalar=1.5)
    df = pd.concat([df, bb, kc], axis=1)
    try:
        bbl = [c for c in df.columns if c.startswith('BBL_')][0]
        kcl = [c for c in df.columns if c.startswith('KCL') or c.startswith('KCLe')][0]
        df['Squeeze_On'] = df[bbl] > df[kcl]
    except Exception:
        # 볼린저/켈트너 컬럼 이름이 안 잡히면 스퀴즈는 꺼진 것으로 본다
        df['Squeeze_On'] = False

    # 4. 수급(CVD)
    vol_delta = np.where(df['close'] > df['open'], df['volume'] * 0.6, -df['volume'] * 0.6)
    df['CVD'] = ta.ema(pd.Series(vol_delta, index=df.index), length=14)
    df['CVD_Signal'] = ta.sma(df['CVD'], length=9)
    return df.ffill().bfill()