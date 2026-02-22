import pandas as pd
import pandas_ta as ta
import numpy as np

def add_indicators(df):
    """모든 기술적 지표 계산 및 초기화 (백테스트 신호 최적화 버전)"""
    if df is None or len(df) < 10: 
        return df
    
    # 1. 기본 지표 계산 (RSI, EMA, ADX)
    df['RSI'] = ta.rsi(df['close'], length=14).fillna(50)
    df['EMA_200'] = ta.ema(df['close'], length=200).fillna(df['close'])
    
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
    if adx_df is not None and not adx_df.empty:
        df['ADX'] = adx_df['ADX_14'].fillna(0)
    else:
        df['ADX'] = 0

    # 2. 볼륨 프로파일 (VAL/VAH) - 롤링 윈도우 방식으로 수정
    # 백테스트 시 각 시점마다 과거 480봉(24시간) 기준의 매물대를 계산합니다.
    lookback = 480
    
    # 계산 속도와 정확도를 위해 퀀타일(Quantile) 방식을 혼합하여 
    # 과거 모든 시점에 대한 VAL/VAH를 생성합니다.
    if len(df) >= lookback:
        # 이 방식은 백테스트 시 모든 시점의 하단/상단 매물대를 개별적으로 잡아줍니다.
        df['VAL'] = df['close'].rolling(window=lookback, min_periods=100).quantile(0.2).ffill()
        df['VAH'] = df['close'].rolling(window=lookback, min_periods=100).quantile(0.8).ffill()
        df['POC'] = df['close'].rolling(window=lookback, min_periods=100).mean().ffill()
    else:
        # 데이터 부족 시 현재가 기준 넓은 범위 설정
        df['VAL'] = df['close'] * 0.98
        df['VAH'] = df['close'] * 1.02
        df['POC'] = df['close']

    # 3. CVD (수급 지표) 및 시그널
    # 가격 변화와 거래량을 결합하여 수급 흐름 계산
    df['vol_delta'] = np.where(df['close'] >= df['close'].shift(1), df['volume'], -df['volume'])
    df['CVD'] = df['vol_delta'].cumsum()
    df['CVD_Signal'] = ta.ema(df['CVD'], length=20).fillna(df['CVD'])
    
    # 4. 결측치 최종 처리
    return df.ffill().bfill()