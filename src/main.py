import time
from fetcher import fetch_historical_data
from indicators import add_indicators
from strategy import apply_strategy
import pandas_ta_classic as ta

def run_bot():
    print("🧪 [테스트 모드] 스나이퍼 자동매매 데이터 검증 가동...")
    # API 연결(get_exchange) 부분을 주석 처리하여 키 없이도 실행되게 합니다.
    # exchange = get_exchange() 
    
    while True:
        try:
            # 1. 최신 데이터 수집 (3분봉)
            df = fetch_historical_data(limit=300)
            
            # 2. 지훈님의 볼륨 프로파일 및 지표 계산
            df = add_indicators(df)
            
            # 3. 최적화된 황금 수치(EMA 30) 적용 전략 실행
            df = apply_strategy(df, ema_len=30)
            
            last = df.iloc[-1]
            current_time = last.name
            
            # 4. 타점 포착 로그 출력 (데이터가 정확한지 여기서 확인)
            if last['Long_Signal']:
                print(f"🎯 [타점 포착!] 시간: {current_time} | 가격: {last['close']}")
                print(f"   👉 회색선(POC): {last['POC']:.2f} | 파란선(VAL): {last['VAL']:.2f}")
                print(f"   👉 현재 상태: 매물대 하단 이탈 및 RSI 다이버전스 컨펌 완료")
            else:
                # 작동 중임을 알리기 위한 일반 로그
                print(f"🔍 [감시 중] {current_time} | 가격: {last['close']} | 시그널 대기 중...")
            
            # 3분봉이므로 3분(180초) 대기
            time.sleep(180) 
            
        except Exception as e:
            print(f"⚠️ 테스트 중 오류 발생: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_bot()