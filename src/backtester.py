import vectorbt as vbt
import os
from fetcher import fetch_historical_data
from indicators import add_indicators
from strategy import apply_strategy

def run_test():
    print("📊 통합 백테스트 시작...")
    df = fetch_historical_data(limit=2000)
    df = apply_strategy(add_indicators(df))
    
    pf = vbt.Portfolio.from_signals(
        df['close'], entries=df['Long_Signal'], exits=None,
        tp_stop=0.02, sl_stop=0.01, fees=0.00075, freq='3m'
    )
    
    print(pf.stats())
    os.makedirs('data', exist_ok=True)
    pf.plot().write_image("data/backtest_result.png")
    print("✅ 분석 완료 (data/backtest_result.png 저장됨)")

if __name__ == "__main__":
    run_test()