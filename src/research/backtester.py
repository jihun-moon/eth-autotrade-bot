import vectorbt as vbt
import importlib, os, sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
import strategies.strategy as strategy

def run_final_test():
    print("📊 [최종 검증] 전략 분석 중...")
    df = add_indicators(fetch_historical_data(limit=5000))
    importlib.reload(strategy)
    res = strategy.apply_strategy(df)
    df_res, params = res if isinstance(res, tuple) else (res, {'tp': 0.02, 'sl': 0.015})
    
    pf = vbt.Portfolio.from_signals(df_res['close'], entries=df_res.get('Long_Signal', False), 
                                   short_entries=df_res.get('Short_Signal', False), 
                                   tp_stop=params['tp'], sl_stop=params['sl'], freq='3m', init_cash=10000)
    print(f"\n{pf.stats()}")

if __name__ == "__main__":
    run_final_test()