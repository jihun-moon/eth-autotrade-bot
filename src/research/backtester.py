import vectorbt as vbt
from fetcher import fetch_historical_data
from indicators import add_indicators
from strategy import apply_strategy

def run_final_test():
    print("📊 [최종 검증] 양방향(LONG/SHORT) 전략 성적표 도출 중...")
    df = fetch_historical_data(limit=5000)
    df = apply_strategy(add_indicators(df))
    
    # 🌟 숏(Short) 진입 조건 추가 완료
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df['Long_Signal'],        # 롱 진입
        short_entries=df['Short_Signal'], # 숏 진입
        exits=None,
        short_exits=None,
        tp_stop=0.02, 
        sl_stop=0.01, 
        fees=0.00075, 
        freq='3m'
    )
    
    print("\n" + "="*50)
    print("📈 ETH 스나이퍼 양방향 전략 최종 성적표")
    print(pf.stats())
    print("="*50)

if __name__ == "__main__":
    run_final_test()