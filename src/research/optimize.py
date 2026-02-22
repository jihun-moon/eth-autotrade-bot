import vectorbt as vbt
import pandas as pd
import numpy as np
from fetcher import fetch_historical_data
from indicators import add_indicators
from strategy import apply_strategy

def run_optimization():
    print("🔎 [최적화 엔진] 최고의 수익률을 내는 양방향 수치 조합을 찾는 중...")
    
    raw_df = fetch_historical_data(symbol='ETH/USDT', timeframe='3m', limit=5000)
    df_base = add_indicators(raw_df)
    
    ema_list = [30, 50, 100, 200]      
    tp_list = [0.01, 0.015, 0.02, 0.03] 
    sl_list = [0.005, 0.01, 0.015]      
    
    results = []

    for ema in ema_list:
        df = apply_strategy(df_base.copy(), ema_len=ema)
        entries = df['Long_Signal']
        short_entries = df['Short_Signal'] # 🌟 숏 시그널 가져오기
        
        for tp in tp_list:
            for sl in sl_list:
                # 🌟 롱과 숏 모두 포트폴리오에 반영
                pf = vbt.Portfolio.from_signals(
                    df['close'], 
                    entries=entries, 
                    short_entries=short_entries, 
                    exits=None, 
                    short_exits=None,
                    tp_stop=tp, sl_stop=sl, init_cash=10000,
                    fees=0.00075, freq='3m'
                )
                
                results.append({
                    'EMA': ema,
                    'TP_pct': tp * 100,
                    'SL_pct': sl * 100,
                    'Return_pct': pf.total_return() * 100,
                    'Trades': pf.trades.count()
                })

    res_df = pd.DataFrame(results).sort_values(by='Return_pct', ascending=False)
    
    print("\n" + "="*70)
    print(f"🏆 [양방향 전략 최적화 TOP 10] (분석 기간: {len(raw_df)}캔들)")
    print(res_df.head(10).to_string(index=False))
    print("="*70)

if __name__ == "__main__":
    run_optimization()