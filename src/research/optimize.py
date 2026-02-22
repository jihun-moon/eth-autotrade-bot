import vectorbt as vbt
import pandas as pd
import numpy as np
import os
import sys

# 🌟 경로 설정: 상위 폴더(src)를 임포트 경로에 추가하여 utils, strategies를 찾을 수 있게 함
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
import strategies.strategy as strategy

def run_optimization():
    print("🔎 [최적화 엔진] 최적의 파라미터 조합을 찾는 중...")
    
    # 1. 데이터 준비 (최근 5000캔들, 약 10일치)
    raw_df = fetch_historical_data(symbol='ETH/USDT', timeframe='3m', limit=5000)
    if raw_df is None or raw_df.empty:
        print("❌ 데이터를 가져오는데 실패했습니다.")
        return
    df_base = add_indicators(raw_df)
    
    # 2. 최적화할 수치 범위 설정
    ema_list = [30, 50, 100]      
    tp_list = [0.015, 0.02, 0.025, 0.03] 
    sl_list = [0.01, 0.015, 0.02]      
    
    results = []

    # 3. 그리드 서치(Grid Search) 실행
    for ema in ema_list:
        # 🌟 현재 전략은 (df, params) 튜플을 반환하므로 분리해서 받음
        res = strategy.apply_strategy(df_base.copy(), ema_len=ema)
        if isinstance(res, tuple):
            df_strat, _ = res
        else:
            df_strat = res
        
        entries = df_strat.get('Long_Signal', False)
        short_entries = df_strat.get('Short_Signal', False)
        
        for tp in tp_list:
            for sl in sl_list:
                # 🌟 벡터비티 포트폴리오 생성
                # 중요: 오픈소스 vbt(0.28.1)는 leverage 인자를 지원하지 않으므로 삭제합니다.
                pf = vbt.Portfolio.from_signals(
                    df_strat['close'], 
                    entries=entries, 
                    short_entries=short_entries, 
                    tp_stop=tp, 
                    sl_stop=sl, 
                    init_cash=10000,
                    fees=0.0005, # 실전 수수료 반영
                    freq='3m'
                )
                
                results.append({
                    'EMA': ema,
                    'TP(%)': tp * 100,
                    'SL(%)': sl * 100,
                    'Return(%)': pf.total_return() * 100,
                    'WinRate(%)': pf.trades.win_rate() * 100,
                    'Trades': pf.trades.count()
                })

    # 4. 결과 정리 및 출력
    res_df = pd.DataFrame(results).sort_values(by='Return(%)', ascending=False)
    
    print("\n" + "="*80)
    print(f"🏆 [ETH 전략 최적화 TOP 10] (분석 기간: {len(raw_df)} 캔들)")
    print(res_df.head(10).to_string(index=False))
    print("="*80)
    
    # 최적의 조합 안내
    best = res_df.iloc[0]
    print(f"\n💡 최적 조합 제안: EMA {int(best['EMA'])}, TP {best['TP(%)']:.1f}%, SL {best['SL(%)']:.1f}%")
    print(f"📈 기대 수익률 (1배율 기준): {best['Return(%)']:.2f}%")
    print(f"🚀 실전(10배 레버리지) 예상 수익률: {best['Return(%)'] * 10:.2f}%")

if __name__ == "__main__":
    run_optimization()