import vectorbt as vbt
import importlib, os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
import strategies.strategy as strategy

def run_final_test():
    print("📊 [최종 검증] 15분봉 스윙 전략 분석 중...")
    # 🌟 15m 데이터 수집
    df = add_indicators(fetch_historical_data(timeframe='15m', limit=5000))
    importlib.reload(strategy)
    df_res, params = strategy.apply_strategy(df)
    
    pf = vbt.Portfolio.from_signals(
        df_res['close'], 
        entries=(df_res['Signal'] == 1), 
        short_entries=(df_res['Signal'] == -1), 
        tp_stop=params['tp'], 
        sl_stop=params['sl'], 
        freq='15m', # 🌟 15m 반영
        init_cash=10000,
        fees=0.0004  # 🌟 수수료 반영
    )
    print(f"\n{pf.stats()}")

if __name__ == "__main__":
    run_final_test()