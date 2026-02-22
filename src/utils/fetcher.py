import ccxt
import pandas as pd
import os, time

def fetch_historical_data(symbol='ETH/USDT', timeframe='3m', limit=5000):
    exchange = ccxt.binance()
    raw_path = f"data/raw/{symbol.replace('/', '_')}_{timeframe}.csv"
    os.makedirs("data/raw", exist_ok=True)
    
    since = None
    if os.path.exists(raw_path):
        df_local = pd.read_csv(raw_path, index_col=0, parse_dates=True)
        if not df_local.empty: since = int(df_local.index[-1].timestamp() * 1000) + 1

    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
    if ohlcv:
        df_new = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_new['timestamp'] = pd.to_datetime(df_new['timestamp'], unit='ms')
        df_new.set_index('timestamp', inplace=True)
        df_local = pd.concat([df_local, df_new]).drop_duplicates().sort_index() if 'df_local' in locals() else df_new
        df_local.to_csv(raw_path)
        
    return df_local.tail(limit)