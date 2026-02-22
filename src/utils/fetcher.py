import ccxt
import pandas as pd
import os
import time
import logging

logger = logging.getLogger("BottomScanner")

def fetch_historical_data(symbol='ETH/USDT', timeframe='3m', limit=5000):
    """증분 수집 및 재시도 로직이 강화된 데이터 수집기"""
    exchange = ccxt.binance()
    raw_path = f"data/raw/{symbol.replace('/', '_')}_{timeframe}.csv"
    os.makedirs("data/raw", exist_ok=True)

    # 1. 로컬 데이터 로드
    df_local = pd.DataFrame()
    since = None
    if os.path.exists(raw_path):
        df_local = pd.read_csv(raw_path, index_index=0, parse_dates=True)
        if not df_local.empty:
            since = int(df_local.index[-1].timestamp() * 1000) + 1

    # 2. 데이터 수집 (네트워크 에러 재시도 로직 포함)
    all_ohlcv = []
    attempts = 0
    max_retries = 5

    while len(all_ohlcv) < limit:
        try:
            fetch_limit = min(1000, limit - len(all_ohlcv))
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=fetch_limit)
            
            if not ohlcv: break
            
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            attempts = 0 # 성공 시 횟수 초기화
            time.sleep(0.1)
            
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            attempts += 1
            if attempts > max_retries:
                logger.error(f"❌ 최대 재시도 횟수 초과: {e}")
                break
            wait_time = 2 ** attempts # 지수 백오프
            logger.warning(f"⚠️ 네트워크 오류. {wait_time}초 후 재시도... ({attempts}/{max_retries})")
            time.sleep(wait_time)

    # 3. 데이터 병합 및 저장
    if all_ohlcv:
        df_new = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_new['timestamp'] = pd.to_datetime(df_new['timestamp'], unit='ms')
        df_new.set_index('timestamp', inplace=True)
        df_combined = pd.concat([df_local, df_new]).drop_duplicates().sort_index()
        df_combined.to_csv(raw_path)
        return df_combined.tail(limit)
    
    return df_local.tail(limit)