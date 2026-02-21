import vectorbt as vbt
import pandas as pd
import numpy as np
from fetcher import fetch_historical_data
from indicators import add_indicators
from strategy import apply_strategy

def run_optimization():
    print("🔎 [최적화 엔진] 모든 조합을 테스트하여 최고의 수치를 찾는 중...")
    
    # 1. 데이터 수집 (분석을 위해 5000개 권장)
    raw_df = fetch_historical_data(symbol='ETH/USDT', timeframe='3m', limit=5000)
    df_base = add_indicators(raw_df)
    
    # 2. 테스트할 파라미터 범위 (지훈님이 궁금한 숫자를 마음껏 넣으세요)
    ema_list = [30, 50, 100]           # 테스트할 EMA 기간
    tp_list = [0.01, 0.015, 0.02]      # 테스트할 익절 % (1%, 1.5%, 2%)
    sl_list = [0.005, 0.01]            # 테스트할 손절 % (0.5%, 1%)
    
    results = []

    # 3. 모든 조합 시뮬레이션
    for ema in ema_list:
        # EMA 기간별로 전략 시그널 생성
        df = apply_strategy(df_base.copy(), ema_len=ema)
        entries = df['Long_Signal']
        
        for tp in tp_list:
            for sl in sl_list:
                # 각 익절/손절 조합별 백테스트
                pf = vbt.Portfolio.from_signals(
                    df['close'],
                    entries=entries,
                    exits=None,
                    tp_stop=tp,
                    sl_stop=sl,
                    init_cash=10000,
                    fees=0.00075,
                    freq='3m'
                )
                
                # 결과 수집 (pf.trades.count()로 에러 수정)
                results.append({
                    'EMA': ema,
                    'TP_pct': tp * 100,
                    'SL_pct': sl * 100,
                    'Return_pct': pf.total_return() * 100,
                    'Trade_Count': pf.trades.count() # 👈 에러 수정된 부분
                })

    # 4. 결과 출력 (수익률 높은 순 정렬)
    res_df = pd.DataFrame(results).sort_values(by='Return_pct', ascending=False)
    
    print("\n" + "="*70)
    print(f"🏆 [최적화 결과 TOP 10] (데이터: {len(raw_df)}캔들)")
    print(res_df.head(10).to_string(index=False))
    print("="*70)
    print("\n💡 팁: Return_pct가 플러스이면서 Trade_Count(거래횟수)가 너무 적지 않은 것을 선택하세요.")

if __name__ == "__main__":
    run_optimization()