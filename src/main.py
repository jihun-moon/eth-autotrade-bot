import time
import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv
from fetcher import fetch_historical_data
from indicators import add_indicators
from strategy import apply_strategy

# .env 파일의 환경 변수를 불러옵니다
load_dotenv()

# 텔레그램 설정값 ( .env에 적은 값을 가져옴 )
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BOT_NAME = "Bottom-Scanner"  # 지훈님이 정하신 이름을 여기에 적으세요!

async def send_telegram_msg(message):
    """텔레그램으로 메시지를 보내는 함수"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        full_msg = f"[{BOT_NAME}]\n{message}"
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=full_msg)
    except Exception as e:
        print(f"❌ 텔레그램 알림 전송 실패: {e}")

def run_bot():
    print(f"🚀 [{BOT_NAME}] 실전 모드 가동! 텔레그램 알림이 활성화되었습니다.")
    
    # --- 아래 한 줄을 추가하여 시작 알림을 보냅니다 ---
    asyncio.run(send_telegram_msg(f"✅ {BOT_NAME} 연결 성공! 지금부터 이더리움 바닥 낚시를 시작합니다."))
    # -----------------------------------------------
    
    while True:
        try:
            # 1. 최신 데이터 수집 (3분봉)
            df = fetch_historical_data(limit=600)
            
            # 2. 지표 계산 (lookback 480 반영된 indicators.py 호출)
            df = add_indicators(df)
            
            # 3. 매물대 낚시 전략 실행
            df = apply_strategy(df, ema_len=30)
            
            last = df.iloc[-1]
            current_time = last.name
            
            # 4. 타점 포착 시 텔레그램 알림 전송
            if last['Long_Signal']:
                msg = (f"🎯 [타점 포착!]\n"
                       f"⏰ 시간: {current_time}\n"
                       f"💰 가격: {last['close']}\n"
                       f"📊 회색선(POC): {last['POC']:.2f}\n"
                       f"📉 파란선(VAL): {last['VAL']:.2f}\n"
                       f"👉 현재 상태: 매물대 하단 이탈 및 반등 컨펌!")
                print(msg)
                
                # 비동기 함수인 텔레그램 전송 실행
                asyncio.run(send_telegram_msg(msg))
            else:
                # 작동 중임을 알리기 위한 로그
                print(f"🔍 [감시 중] {current_time} | 가격: {last['close']} | 시그널 대기 중...")
            
            # 3분봉이므로 3분(180초) 대기
            time.sleep(180) 
            
        except Exception as e:
            print(f"⚠️ 에러 발생: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_bot()