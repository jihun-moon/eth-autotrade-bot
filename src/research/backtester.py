import vectorbt as vbt
import importlib
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
import strategies.strategy as strategy

def run_final_test():
    print("📊 [최종 검증] 양방향 동적 TP/SL 전략 성적표 도출 중...")
    
    # 1. 데이터 준비
    raw_df = fetch_historical_data(limit=5000)
    df_ind = add_indicators(raw_df)
    
    # 2. 전략 실행 (컬럼 및 파라미터 수신)
    importlib.reload(strategy)
    df, d_params = strategy.apply_strategy(df_ind)
    
    print(f"💡 현재 시점 기준 타겟 - TP: {d_params['tp']*100:.2f}%, SL: {d_params['sl']*100:.2f}%")
    
    # 3. 컬럼 기반 백테스트 실행
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df['Long_Signal'],        
        short_entries=df['Short_Signal'], 
        exits=None,
        short_exits=None,
        tp_stop=df['target_tp'], # 🌟 시점별 동적 익절 적용
        sl_stop=df['target_sl'], # 🌟 시점별 동적 손절 적용
        fees=0.00075, 
        slippage=0.001,          # 실전 슬리피지 반영
        freq='3m'
    )
    
    print("\n" + "="*50)
    print("📈 ETH 스나이퍼 양방향 전략 최종 성적표 (ATR 동적 컬럼 모드)")
    print(pf.stats())
    print("="*50)

if __name__ == "__main__":
    run_final_test()