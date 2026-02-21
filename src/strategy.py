import pandas as pd
import numpy as np
import os
from indicators import add_indicators 

def apply_strategy(df):
    print("🧠 매매 전략 v2.0 (파인스크립트 룰 완벽 적용) 탐색 중...")
    
    # 1. 기존 필터 (추세, 수급, 스퀴즈)
    trend_long = df['close'] > df['EMA_50']
    trend_short = df['close'] < df['EMA_50']
    cvd_long = df['CVD'] > df['CVD_Signal']
    cvd_short = df['CVD'] < df['CVD_Signal']
    volatility_ok = df['Squeeze_On'] == False
    
    # 🌟 2. 신규: 거래량 컨펌 필터 (SMA 20)
    df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
    volume_ok = df['volume'] > df['Vol_SMA']
    
    # 🌟 3. 신규: 최근 파동의 고점(Swing High)과 저점(Swing Low) 계산 (피보나치용)
    # 파인스크립트의 pivot_lookback 기간(대략 10캔들)을 참고
    df['Swing_High'] = df['high'].rolling(window=10).max()
    df['Swing_Low'] = df['low'].rolling(window=10).min()
    
    # 4. RSI 다이버전스 (타점)
    lookback = 5
    df['Low_Min'] = df['low'].rolling(window=lookback).min()
    df['High_Max'] = df['high'].rolling(window=lookback).max()
    df['RSI_Min'] = df['RSI_14'].rolling(window=lookback).min()
    df['RSI_Max'] = df['RSI_14'].rolling(window=lookback).max()
    
    bullish_div = (df['low'] == df['Low_Min']) & (df['RSI_14'] > df['RSI_Min'].shift(1))
    bearish_div = (df['high'] == df['High_Max']) & (df['RSI_14'] < df['RSI_Max'].shift(1))
    
    # 5. 최종 시그널 (거래량 조건 추가!)
    df['Long_Signal'] = bullish_div & cvd_long & volatility_ok & trend_long & volume_ok
    df['Short_Signal'] = bearish_div & cvd_short & volatility_ok & trend_short & volume_ok
    
    return df

if __name__ == "__main__":
    file_path = '../data/eth_15m_historical.csv' if os.path.exists('../data/eth_15m_historical.csv') else 'data/eth_15m_historical.csv'
    if os.path.exists(file_path):
        raw_df = pd.read_csv(file_path, index_col='timestamp', parse_dates=True)
        final_df = apply_strategy(add_indicators(raw_df))
        long_hits = final_df[final_df['Long_Signal'] == True]
        print(f"\n🎯 깐깐해진 볼륨 필터 통과 후 남은 롱 타점: {len(long_hits)}번")
    else:
        print("❌ CSV 파일 없음.")