import ccxt
import pandas as pd
import os

def fetch_historical_data(symbol='ETH/USDT', timeframe='3m', limit=1000):
    """바이낸스 과거 OHLCV 데이터 수집"""
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Seoul')
    df.set_index('timestamp', inplace=True)
    return df