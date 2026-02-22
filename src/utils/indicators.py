import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    """모든 기술적 지표 계산 (실전/백테스트 공용 완성본)"""
    if df is None or len(df) < 10: 
        return df
    
    # 1. 기본 지표 (RSI, EMA, ADX)
    df['RSI'] = ta.rsi(df['close'], length=14).fillna(50)
    df['EMA_200'] = ta.ema(df['close'], length=200).fillna(df['close'])
    
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
    if adx_df is not None and not adx_df.empty:
        df['ADX'] = adx_df['ADX_14'].fillna(0)
    else:
        df['ADX'] = 0

    # 2. 볼륨 프로파일 (VAL/VAH) - 롤링 윈도우 (과거 24시간 기준)
    # 백테스트 시 모든 캔들에 대해 과거 데이터를 기반으로 매물대를 계산합니다.
    lookback = 480
    df['VAL'] = df['close'].rolling(window=lookback, min_periods=100).quantile(0.2)
    df['VAH'] = df['close'].rolling(window=lookback, min_periods=100).quantile(0.8)
    df['POC'] = df['close'].rolling(window=lookback, min_periods=100).mean()
    
    # 데이터 초반 결측치는 현재가 기준으로 방어
    df['VAL'] = df['VAL'].fillna(df['close'] * 0.98)
    df['VAH'] = df['VAH'].fillna(df['close'] * 1.02)
    df['POC'] = df['POC'].fillna(df['close'])

    # 3. CVD (수급 지표)
    df['vol_delta'] = np.where(df['close'] >= df['close'].shift(1), df['volume'], -df['volume'])
    df['CVD'] = df['vol_delta'].cumsum()
    df['CVD_Signal'] = ta.ema(df['CVD'], length=20).fillna(df['CVD'])
    
    # 4. 최종 결측치 처리
    return df.ffill().bfill()