import vectorbt as vbt
import pandas as pd
import os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
import strategies.strategy as strategy

def run_optimization():
    print("🔎 최적 조합 찾는 중...")
    df_base = add_indicators(fetch_historical_data(limit=5000))
    ema_list, tp_list = [30, 50, 100], [0.015, 0.02, 0.025]
    results = []

    for ema in ema_list:
        df_strat, _ = strategy.apply_strategy(df_base.copy(), ema_len=ema)
        for tp in tp_list:
            pf = vbt.Portfolio.from_signals(df_strat['close'], entries=df_strat.get('Long_Signal', False), 
                                           short_entries=df_strat.get('Short_Signal', False), 
                                           tp_stop=tp, sl_stop=0.015, freq='3m')
            results.append({'EMA': ema, 'TP': tp, 'Return': pf.total_return() * 100})
            
    print(pd.DataFrame(results).sort_values(by='Return', ascending=False).head(5))

if __name__ == "__main__":
    run_optimization()