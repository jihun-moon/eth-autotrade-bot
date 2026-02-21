import time
from fetcher import fetch_historical_data
from indicators import add_indicators
from strategy import apply_strategy
from trader import get_exchange
import pandas_ta as ta

def run_bot():
    print("🚀 스나이퍼 자동매매 가동...")
    exchange = get_exchange()
    
    while True:
        try:
            df = fetch_historical_data(limit=300)
            df = add_indicators(df)
            df = apply_strategy(df)
            
            last = df.iloc[-1]
            if last['Long_Signal']:
                print(f"🎯 타점 포착! 가격: {last['close']} | 회색선(POC): {last['POC']}")
                # exchange.create_market_buy_order('ETH/USDT', amount) # 실전 시 주석 해제
            
            time.sleep(180) # 3분 대기
        except Exception as e:
            print(f"❌ 에러: {e}"); time.sleep(10)

if __name__ == "__main__":
    run_bot()