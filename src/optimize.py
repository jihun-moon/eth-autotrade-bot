import vectorbt as vbt
import pandas as pd
import numpy as np
from fetcher import fetch_historical_data
from indicators import add_indicators
from strategy import apply_strategy

def run_optimization():
    print("🔎 [최적화 엔진] 최고의 수익률을 내는 수치 조합을 찾는 중...")
    
    # 1. 데이터 수집 (안정적인 통계를 위해 5,000개 권장)
    raw_df = fetch_historical_data(symbol='ETH/USDT', timeframe='3m', limit=5000)
    df_base = add_indicators(raw_df)
    
    # 2. 테스트할 파라미터 범위 설정
    ema_list = [30, 50, 100, 200]      # EMA 기간 후보
    tp_list = [0.01, 0.015, 0.02, 0.03] # 익절 % (1% ~ 3%)
    sl_list = [0.005, 0.01, 0.015]      # 손절 % (0.5% ~ 1.5%)
    
    results = []

    # 3. 모든 조합 시뮬레이션 (Grid Search)
    for ema in ema_list:
        df = apply_strategy(df_base.copy(), ema_len=ema)
        entries = df['Long_Signal']
        
        for tp in tp_list:
            for sl in sl_list:
                # 각 조합별 백테스트 실행
                pf = vbt.Portfolio.from_signals(
                    df['close'], entries=entries, exits=None,
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

    # 4. 결과 출력 (수익률 높은 순)
    res_df = pd.DataFrame(results).sort_values(by='Return_pct', ascending=False)
    
    print("\n" + "="*70)
    print(f"🏆 [전략 최적화 TOP 10] (분석 기간: {len(raw_df)}캔들)")
    print(res_df.head(10).to_string(index=False))
    print("="*70)
    print("\n💡 Tip: 수익률(Return_pct)이 높으면서 거래 횟수(Trades)가 적절한 수치를 고르세요!")

if __name__ == "__main__":
    run_optimization()