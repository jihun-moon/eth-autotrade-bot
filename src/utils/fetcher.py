import ccxt
import pandas as pd
import os
import time

def fetch_historical_data(symbol='ETH/USDT', timeframe='3m', limit=5000):
    """바이낸스 API의 1000개 제한을 뚫고 반복문으로 limit만큼 가져오기"""
    exchange = ccxt.binance()
    all_ohlcv = []
    until = None 
    
    print(f"📥 데이터 수집 시작... (목표: {limit}캔들)")
    
    while len(all_ohlcv) < limit:
        # 바이낸스 최대치인 1000개씩 끊어서 요청
        fetch_limit = min(1000, limit - len(all_ohlcv))
        
        # 특정 시점(until) 이전 데이터를 요청
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=fetch_limit, params={'until': until} if until else {})
        
        if not ohlcv:
            break
            
        all_ohlcv.extend(ohlcv)
        until = ohlcv[0][0] - 1  # 가장 오래된 데이터보다 더 이전 시점으로 설정
        
        time.sleep(0.1) # API 차단 방지용 짧은 휴식
        print(f"✅ 현재 {len(all_ohlcv)}개 확보 중...")

    # 시간순으로 정렬 (거꾸로 가져왔으므로)
    all_ohlcv.sort(key=lambda x: x[0])
    
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Seoul')
    df.set_index('timestamp', inplace=True)
    
    # 중복 데이터 제거 및 최종 개수 조절
    df = df[~df.index.duplicated(keep='first')]
    return df.tail(limit)