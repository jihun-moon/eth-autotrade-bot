import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    if df is None or len(df) < 200: return df
    
    # 1. 기본 지표 (RSI, EMA, ADX)
    df['RSI'] = ta.rsi(df['close'], length=14).fillna(50)
    df['EMA_200'] = ta.ema(df['close'], length=200).fillna(df['close'])
    df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14'].fillna(0)

    # 2. 볼륨 프로파일 (트레이딩뷰 Stable 버전 로직 이식)
    lookback = 480 # 최근 24시간 (15분봉 기준도 동일하게 유지 가능)
    bins = 100     # 트레이딩뷰와 동일한 해상도 설정
    
    if len(df) >= lookback:
        window = df.iloc[-lookback:].copy()
        high_max = window['high'].max()
        low_min = window['low'].min()
        price_interval = (high_max - low_min) / (bins - 1)
        
        if price_interval == 0: price_interval = 0.01
        
        # 🌟 트레이딩뷰 방식: 가격 범위에 거래량 분배
        vols = np.zeros(bins)
        for _, row in window.iterrows():
            # 캔들의 고가~저가가 걸치는 구간(bin) 계산
            start_bin = int((row['low'] - low_min) / price_interval)
            end_bin = int((row['high'] - low_min) / price_interval)
            
            # 해당 범위의 모든 bin에 거래량 합산 (트레이딩뷰 방식)
            for j in range(max(0, start_bin), min(bins, end_bin + 1)):
                vols[j] += row['volume']

        # POC 계산 (가장 거래량이 많은 지점)
        poc_idx = np.argmax(vols)
        df['POC'] = low_min + (poc_idx * price_interval)
        
        # 가치 영역(VA) 계산 (70% 기준)
        va_target = vols.sum() * 0.7
        current_v, l, r = vols[poc_idx], poc_idx, poc_idx
        
        while current_v < va_target and (l > 0 or r < bins - 1):
            lv = vols[l-1] if l > 0 else 0
            rv = vols[r+1] if r < bins - 1 else 0
            if lv >= rv:
                current_v += lv
                l -= 1
            else:
                current_v += rv
                r += 1
        
        df['VAL'] = low_min + (l * price_interval)
        df['VAH'] = low_min + (r * price_interval)
    else:
        # 데이터 부족 시 기본 분위수로 대체
        df['VAL'], df['VAH'], df['POC'] = df['close'].quantile(0.2), df['close'].quantile(0.8), df['close'].median()

    # 3. 스퀴즈 모멘텀 및 수급(CVD) 로직 유지
    bb = ta.bbands(df['close'], length=20, std=2.0)
    kc = ta.kc(df['high'], df['low'], df['close'], length=20, scalar=1.5)
    df = pd.concat([df, bb, kc], axis=1)
    
    try:
        bbl = [c for c in df.columns if c.startswith('BBL_')][0]
        kcl = [c for c in df.columns if c.startswith('KCL') or c.startswith('KCLe')][0]
        df['Squeeze_On'] = df[bbl] > df[kcl]
    except:
        df['Squeeze_On'] = False

    vol_delta = np.where(df['close'] > df['open'], df['volume'] * 0.6, -df['volume'] * 0.6)
    df['CVD'] = ta.ema(pd.Series(vol_delta, index=df.index), length=14)
    df['CVD_Signal'] = ta.sma(df['CVD'], length=9)
    
    return df.ffill().bfill()