import vectorbt as vbt
import importlib
import os
import sys

# 🌟 경로 설정: 실행 위치에 상관없이 src 폴더를 인식하도록 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
import strategies.strategy as strategy

def run_final_test():
    print("📊 [최종 검증] 전략 성적표 도출 중...")
    
    # 1. 데이터 준비 (최근 5000캔들 수집)
    raw_df = fetch_historical_data(limit=5000)
    df_ind = add_indicators(raw_df)
    
    # 2. 전략 실행 (최신 코드 리로드 및 데이터 수신)
    importlib.reload(strategy)
    df, d_params = strategy.apply_strategy(df_ind)
    
    # 🌟 방어 로직: 전략에서 동적 컬럼(target_tp/sl)을 생성하지 않았을 경우를 대비
    tp_val = df['target_tp'] if 'target_tp' in df.columns else d_params.get('tp', 0.02)
    sl_val = df['target_sl'] if 'target_sl' in df.columns else d_params.get('sl', 0.015)
    
    print(f"💡 테스트 파라미터 - 기본 TP: {d_params.get('tp', 0)*100:.2f}%, 기본 SL: {d_params.get('sl', 0)*100:.2f}%")
    
    # 3. 백테스트 실행 (10배 레버리지 반영)
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df.get('Long_Signal', False),        
        short_entries=df.get('Short_Signal', False), 
        tp_stop=tp_val, 
        sl_stop=sl_val, 
        fees=0.0005,    
        slippage=0.0005, 
        freq='3m',
        leverage=10,        # 🌟 10배 레버리지 추가
        leverage_fixed=True
    )
    
    # 4. 결과 출력
    print("\n" + "="*50)
    print("📈 ETH 시스템 트레이딩 최종 성적표")
    # 주요 통계치 출력
    print(pf.stats())
    print("="*50)
    
    # 상세 매매 내역이 있다면 최근 기록 출력
    if pf.trades.count() > 0:
        print("\n[최근 5건 매매 기록]")
        print(pf.trades.records_readable.tail(5))

if __name__ == "__main__":
    run_final_test()