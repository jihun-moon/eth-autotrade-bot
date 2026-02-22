import vectorbt as vbt
# [경로 수정] 패키지 구조에 맞게 임포트 경로 확인 필요
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
from strategies.strategy import apply_strategy

def run_final_test():
    print("📊 [최종 검증] 양방향(LONG/SHORT) 전략 성적표 도출 중...")
    
    # 1. 데이터 수집 및 지표 추가
    raw_df = fetch_historical_data(limit=5000)
    df_ind = add_indicators(raw_df)
    
    # 2. 전략 적용 (수정된 반환 형식 반영)
    df, d_params = apply_strategy(df_ind)
    
    print(f"💡 적용된 동적 타겟 - TP: {d_params['tp']*100:.2f}%, SL: {d_params['sl']*100:.2f}%")
    
    # 3. 포트폴리오 생성
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df['Long_Signal'],        
        short_entries=df['Short_Signal'], 
        exits=None,
        short_exits=None,
        tp_stop=d_params['tp'],   # 🌟 전략에서 제안한 동적 TP 사용
        sl_stop=d_params['sl'],   # 🌟 전략에서 제안한 동적 SL 사용
        fees=0.0005,              # 수수료 최적화 (0.05%)
        slippage=0.001,           # 🌟 실전과 유사하게 0.1% 슬리피지 추가
        freq='3m'
    )
    
    print("\n" + "="*50)
    print("📈 ETH 스나이퍼 양항향 전략 최종 성적표 (ATR 동적 모드)")
    print(pf.stats())
    print("="*50)
    
    # 리포트 저장 (선택 사항)
    # pf.plot().write_image("data/reports/final_test_report.png")

if __name__ == "__main__":
    run_final_test()