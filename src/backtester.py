import vectorbt as vbt
from fetcher import fetch_historical_data
from indicators import add_indicators
from strategy import apply_strategy

def run_final_test():
    print("📊 [최종 검증] 황금 수치(EMA 30, TP 2%, SL 1%) 적용 중...")
    df = fetch_historical_data(limit=1000)
    df = apply_strategy(add_indicators(df))
    
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df['Long_Signal'], 
        exits=None,
        tp_stop=0.02, # 👈 최적화 결과: 익절 2%
        sl_stop=0.01, # 👈 최적화 결과: 손절 1%
        fees=0.00075, # 바이낸스 실질 수수료
        freq='3m'
    )
    
    print("\n" + "="*50)
    print("📈 ETH 스나이퍼 전략 최종 성적표")
    print(pf.stats())
    print("="*50)

if __name__ == "__main__":
    run_final_test()