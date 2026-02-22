import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    """모든 기술적 지표 계산 (Volume Profile 정교화 버전)"""
    if df is None or len(df) < 200: 
        return df
    
    # 1. 기본 지표
    df['RSI'] = ta.rsi(df['close'], length=14).fillna(50)
    df['EMA_200'] = ta.ema(df['close'], length=200).fillna(df['close'])
    
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
    df['ADX'] = adx_df['ADX_14'].fillna(0) if adx_df is not None else 0

    # 2. 정교한 볼륨 프로파일 (VAL/VAH/POC) - 진짜 Volume Profile (Histogram)
    # 롤링 퀀타일 대신 최신 윈도우의 거래량 분포를 히스토그램으로 분석합니다.
    lookback = 480
    if len(df) >= lookback:
        window = df.tail(lookback)
        # 가격 구간을 50개로 나누고 각 구간의 '거래량' 합산
        vols, bin_edges = np.histogram(window['close'], bins=50, weights=window['volume'])
        
        # POC (Point of Control): 거래량이 가장 많이 집중된 가격대
        poc_idx = np.argmax(vols)
        poc_value = (bin_edges[poc_idx] + bin_edges[poc_idx+1]) / 2
        
        # VA (Value Area): POC를 중심으로 전체 거래량의 70%가 집중된 구간 계산
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
        
        # 최신 윈도우에서 계산된 정확한 값을 데이터프레임에 할당
        df['VAL'] = bin_edges[l]
        df['VAH'] = bin_edges[r+1]
        df['POC'] = poc_value
    else:
        # 데이터 부족 시 방어 로직 (이전 방식 하이브리드)
        df['VAL'] = df['close'].rolling(100, min_periods=10).quantile(0.2)
        df['VAH'] = df['close'].rolling(100, min_periods=10).quantile(0.8)
        df['POC'] = df['close'].rolling(100, min_periods=10).mean()

    # 3. CVD (수급 지표) - 단순 누적보다 추세 변화를 읽기 쉽게 신호선 추가
    df['vol_delta'] = np.where(df['close'] >= df['close'].shift(1), df['volume'], -df['volume'])
    df['CVD'] = df['vol_delta'].cumsum()
    df['CVD_Signal'] = ta.ema(df['CVD'], length=20).fillna(df['CVD'])
    
    return df.ffill().bfill()