import ccxt
import pandas as pd
import os
import time
import logging

logger = logging.getLogger("BottomScanner")

def fetch_historical_data(symbol='ETH/USDT', timeframe='15m', limit=5000): # 🌟 기본값 15m 변경
    """증분 수집 로직 및 API 안정성 강화"""
    exchange = ccxt.binance({'enableRateLimit': True})
    raw_path = f"data/raw/{symbol.replace('/', '_')}_{timeframe}.csv"
    os.makedirs("data/raw", exist_ok=True)

    df_local = pd.DataFrame()
    since = None
    
    if os.path.exists(raw_path):
        try:
            df_local = pd.read_csv(raw_path, index_col=0, parse_dates=True)
            if not df_local.empty:
                since = int(df_local.index[-1].timestamp() * 1000) + 1
        except Exception as e:
            logger.error(f"⚠️ 로컬 데이터 로드 실패: {e}")

    all_ohlcv = []
    attempts = 0
    max_retries = 3

    while len(all_ohlcv) < limit:
        try:
            fetch_limit = min(1000, limit - len(all_ohlcv))
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=fetch_limit)
            if not ohlcv: break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            time.sleep(0.1) 
        except Exception as e:
            attempts += 1
            logger.warning(f"⚠️ 데이터 수집 시도 {attempts}/{max_retries} 실패: {e}")
            if attempts >= max_retries: break
            time.sleep(2 ** attempts)

    if all_ohlcv:
        df_new = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_new['timestamp'] = pd.to_datetime(df_new['timestamp'], unit='ms')
        df_new.set_index('timestamp', inplace=True)
        
        if not df_local.empty:
            df_combined = pd.concat([df_local, df_new]).drop_duplicates().sort_index()
        else:
            df_combined = df_new
            
        df_combined.to_csv(raw_path)
        return df_combined.tail(limit)
    
    return df_local.tail(limit)