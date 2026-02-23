import vectorbt as vbt
import pandas as pd
import os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
import strategies.strategy as strategy

def run_optimization():
    print("🔎 15m 스윙 최적 조합 찾는 중...")
    # 🌟 15m 데이터 수집
    df_base = add_indicators(fetch_historical_data(timeframe='15m', limit=5000))
    tp_list = [0.015, 0.02, 0.025, 0.03]
    sl_list = [0.01, 0.012, 0.015]
    results = []

    # 현재 전략은 ema_len을 인자로 받지 않으므로 tp/sl 위주로 테스트
    for tp in tp_list:
        for sl in sl_list:
            df_strat, _ = strategy.apply_strategy(df_base.copy())
            pf = vbt.Portfolio.from_signals(
                df_strat['close'], 
                entries=df_strat.get('Signal') == 1, 
                short_entries=df_strat.get('Signal') == -1, 
                tp_stop=tp, 
                sl_stop=sl, 
                freq='15m', # 🌟 15m 반영
                fees=0.0004  # 🌟 수수료 반영
            )
            results.append({'TP': tp, 'SL': sl, 'Return': pf.total_return() * 100})
            
    print(pd.DataFrame(results).sort_values(by='Return', ascending=False).head(5))

if __name__ == "__main__":
    run_optimization()