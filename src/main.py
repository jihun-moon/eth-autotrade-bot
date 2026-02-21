import os
import asyncio
from datetime import datetime, timedelta
from telegram import Bot
from dotenv import load_dotenv
from fetcher import fetch_historical_data
from indicators import add_indicators
from strategy import apply_strategy
from trader import execute_buy_order, check_my_balance 

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BOT_NAME = "Bottom-Scanner" 

async def send_telegram_msg(message):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        full_msg = f"[{BOT_NAME}]\n{message}"
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=full_msg)
    except Exception as e:
        print(f"❌ 텔레그램 알림 전송 실패: {e}")

async def run_bot():
    print(f"🚀 [{BOT_NAME}] 시그널 전용 모드 가동! (실제 매수 차단됨)")
    
    # 에러 없이 시작 알림 전송
    check_my_balance()
    await send_telegram_msg("✅ 봇 가동 시작!\n(현재 테스트 모드: 실제 매수는 진행되지 않으며 롱 타점 시그널만 전송됩니다.)")

    while True:
        try:
            # 1. 데이터 수집 및 지표/전략 계산
            df = fetch_historical_data(limit=600)
            df = add_indicators(df)
            df = apply_strategy(df, ema_len=30)
            
            last = df.iloc[-1]
            current_time = datetime.now()
            
            # 2. 롱 시그널 포착 시 텔레그램 알림 전송
            if last['Long_Signal']:
                msg = (f"🎯 [롱 타점 포착!]\n"
                       f"⏰ 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                       f"💰 가격: {last['close']}\n"
                       f"👉 매수 시그널 발생! (테스트 모드로 실제 매수는 생략됨)")
                print(msg)
                await send_telegram_msg(msg)
                
                # 매수 함수 호출 (현재 trader.py에서 주석 처리되어 실제 주문은 안 들어감)
                execute_buy_order(symbol='ETH/USDT')
                
            else:
                print(f"🔍 [감시 중] {current_time.strftime('%H:%M:%S')} | 가격: {last['close']} | 시그널 대기 중...")
            
            # 3. 시간 오차(Drift) 방지: 다음 3분봉 캔들 정각까지 남은 초 계산
            now = datetime.now()
            next_run = now.replace(second=0, microsecond=0) + timedelta(minutes=3 - (now.minute % 3))
            sleep_seconds = (next_run - now).total_seconds()
            
            print(f"⏳ 다음 캔들 갱신까지 {int(sleep_seconds)}초 대기...")
            await asyncio.sleep(sleep_seconds)
            
        except Exception as e:
            print(f"⚠️ 봇 실행 중 에러 발생: {e}")
            await asyncio.sleep(10) # 에러 시 10초 대기 후 재시도

if __name__ == "__main__":
    # 비동기 루프 실행
    asyncio.run(run_bot())