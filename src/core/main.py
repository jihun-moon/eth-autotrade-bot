import os
import asyncio
import logging
import importlib
from datetime import datetime, timedelta, timezone
from telegram import Bot
from dotenv import load_dotenv

# [구조 개편] 새 폴더 구조에 맞춘 모듈 임포트
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
import strategies.strategy as strategy 

# [추가] DB 및 트레이더 모듈 임포트
from core.db_manager import init_db, SessionLocal, ActivePosition, TradeHistory
from core.trader import fetch_real_balance, execute_order

# 1. 구조화된 로깅 설정 (콘솔 + 파일 기록)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("data/reports/bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BottomScanner")

load_dotenv()

# 환경 변수 및 설정
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BOT_NAME = "Bottom-Scanner" 
KST = timezone(timedelta(hours=9))

# 매매 파라미터
LEVERAGE = 10             
TP_PCT = 0.02             
SL_PCT = 0.015             

async def send_telegram_msg(message):
    """텔레그램 알림 전송"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"[{BOT_NAME}]\n{message}")
    except Exception as e:
        logger.error(f"❌ 텔레그램 알림 실패: {e}")

async def run_bot():
    # DB 초기화
    init_db()
    db = SessionLocal()
    
    logger.info("🚀 Bottom-Scanner 가동 시작 (DB 복구 및 로깅 엔진 활성화)")
    
    # [복구 로직] DB에서 기존 미결제 포지션 확인
    saved_pos = db.query(ActivePosition).first()
    position = None
    if saved_pos:
        position = {
            'type': saved_pos.pos_type,
            'entry_time': saved_pos.entry_time,
            'entry_price': saved_pos.entry_price,
            'amount': saved_pos.amount,
            'margin': saved_pos.margin,
            'size': saved_pos.amount * saved_pos.entry_price
        }
        logger.info(f"♻️ 포지션 복구 성공: {position['type']} (진입가: {position['entry_price']})")

    await send_telegram_msg(f"✅ 시스템 가동! (서버 재시작 복구 모드 활성화)")

    while True:
        try:
            # 1. 데이터 수집 및 지표 계산
            df_raw = fetch_historical_data(limit=1000)
            df_ind = add_indicators(df_raw)
            
            # 2. 전략 실행 (핫 스와핑 지원)
            importlib.reload(strategy)
            df = strategy.apply_strategy(df_ind.copy())
            last = df.iloc[-1]
            current_price = last['close']

            # 3. 포지션 관리 로직
            if position is None:
                if last['Long_Signal'] or last['Short_Signal']:
                    pos_type = "LONG" if last['Long_Signal'] else "SHORT"
                    
                    # 실전 잔고 조회 및 주문 실행 (trader.py 연동)
                    balance = fetch_real_balance()
                    amount = (balance * LEVERAGE) / current_price
                    
                    # [DB 기록] 포지션 진입 정보 저장
                    new_pos = ActivePosition(
                        pos_type=pos_type, 
                        entry_time=datetime.now(KST),
                        entry_price=current_price, 
                        amount=amount, 
                        margin=balance
                    )
                    db.add(new_pos)
                    db.commit()
                    
                    position = {'type': pos_type, 'entry_price': current_price, 'amount': amount, 'entry_time': datetime.now(KST)}
                    
                    msg = f"🎯 [{pos_type} 진입] 가격: {current_price:.2f} USDT"
                    logger.info(msg)
                    await send_telegram_msg(msg)
            
            else:
                # 수익률(ROE) 계산 및 청산 감시
                if position['type'] == "LONG":
                    roe = (current_price - position['entry_price']) / position['entry_price'] * LEVERAGE
                else:
                    roe = (position['entry_price'] - current_price) / position['entry_price'] * LEVERAGE

                if roe >= (TP_PCT * LEVERAGE) or roe <= -(SL_PCT * LEVERAGE):
                    reason = "익절(TP)" if roe > 0 else "손절(SL)"
                    
                    # [DB 기록] 매매 이력 저장 및 현재 포지션 삭제
                    history = TradeHistory(
                        entry_time=position['entry_time'], 
                        exit_time=datetime.now(KST),
                        pos_type=position['type'], 
                        entry_price=position['entry_price'],
                        exit_price=current_price, 
                        roe_pct=roe*100, 
                        exit_reason=reason
                    )
                    db.add(history)
                    db.query(ActivePosition).delete()
                    db.commit()
                    
                    msg = f"🏁 [{reason} 완료] 최종 ROE: {roe*100:.2f}%"
                    logger.info(msg)
                    await send_telegram_msg(msg)
                    position = None

            # 3분 주기 동기화
            now = datetime.now(KST)
            next_run = now.replace(second=0, microsecond=0) + timedelta(minutes=3 - (now.minute % 3))
            await asyncio.sleep((next_run - now).total_seconds())
            
        except Exception as e:
            logger.error(f"⚠️ 시스템 루프 에러: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_bot())