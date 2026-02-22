import os
import asyncio
import logging
import importlib
from datetime import datetime, timedelta, timezone
from telegram import Bot
from dotenv import load_dotenv

# [모듈 임포트]
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
import strategies.strategy as strategy 
from core.db_manager import init_db, SessionLocal, ActivePosition, TradeHistory
from core.trader import fetch_real_balance, execute_order

# 1. 구조화된 로깅 설정
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
    """텔레그램 알림 전송 공통 함수"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"[{BOT_NAME}]\n{message}")
    except Exception as e:
        logger.error(f"❌ 텔레그램 알림 실패: {e}")

async def heartbeat_loop():
    """1시간마다 봇의 생존 신고 및 현재 시각 보고 (MLOps 모니터링)"""
    while True:
        try:
            now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
            await send_telegram_msg(f"💓 [Heartbeat] 시스템 정상 가동 중\n⏰ 현재시각: {now_str}")
            await asyncio.sleep(3600) # 1시간 대기
        except Exception as e:
            logger.error(f"⚠️ 하트비트 에러: {e}")
            await asyncio.sleep(60)

async def run_bot():
    # [SQL 세팅] DB 초기화 및 테이블 생성 (자동)
    init_db()
    db = SessionLocal()
    
    logger.info("🚀 Bottom-Scanner 가동 시작 (DB 복구 및 섀도우 통합 모드)")
    
    # [복구 로직] DB에서 기존 미결제 포지션 확인
    saved_pos = db.query(ActivePosition).first()
    position = None
    if saved_pos:
        position = {
            'id': saved_pos.id,
            'type': saved_pos.pos_type,
            'entry_time': saved_pos.entry_time,
            'entry_price': saved_pos.entry_price,
            'amount': saved_pos.amount,
            'margin': saved_pos.margin
        }
        logger.info(f"♻️ 포지션 복구 성공: {position['type']} (진입가: {position['entry_price']})")

    # 섀도우 모드용 변수
    shadow_position = None
    TARGET_ROE = TP_PCT * LEVERAGE
    STOPLOSS_ROE = -(SL_PCT * LEVERAGE)

    # 하트비트(생존신고) 루프를 백그라운드에서 실행
    asyncio.create_task(heartbeat_loop())

    await send_telegram_msg(f"✅ 시스템 가동! (복구 모드 및 하트비트 활성화)")

    while True:
        try:
            # 1. 데이터 수집 및 지표 계산
            df_raw = fetch_historical_data(limit=1000)
            df_ind = add_indicators(df_raw)
            
            # 2. 실전 전략 실행 (핫 스와핑 지원)
            importlib.reload(strategy)
            df = strategy.apply_strategy(df_ind.copy())
            last = df.iloc[-1]
            current_price = last['close']

            # --- 3. 섀도우(Shadow) 검증 봇 모니터링 ---
            shadow_strat_path = "src/strategies/strategy_shadow.py"
            if os.path.exists(shadow_strat_path):
                try:
                    import strategies.strategy_shadow as strategy_shadow
                    importlib.reload(strategy_shadow)
                    df_shadow = strategy_shadow.apply_strategy(df_ind.copy())
                    last_shadow = df_shadow.iloc[-1]
                    
                    if shadow_position is None and (last_shadow.get('Long_Signal') or last_shadow.get('Short_Signal')):
                        stype = "LONG" if last_shadow['Long_Signal'] else "SHORT"
                        shadow_position = {'type': stype, 'price': last_shadow['close']}
                        await send_telegram_msg(f"👻 [섀도우 진입] {stype} 포착!\n💰 가격: {last_shadow['close']:.2f}")
                    
                    elif shadow_position is not None:
                        s_roe = ((current_price - shadow_position['price']) / shadow_position['price'] * LEVERAGE 
                                 if shadow_position['type'] == "LONG" else 
                                 (shadow_position['price'] - current_price) / shadow_position['price'] * LEVERAGE)
                        
                        if s_roe >= TARGET_ROE or s_roe <= STOPLOSS_ROE:
                            res = "익절" if s_roe > 0 else "손절"
                            await send_telegram_msg(f"👻 [섀도우 {res}] 결과 보고\n📈 ROE: {s_roe*100:.2f}%")
                            shadow_position = None
                except Exception as se:
                    logger.error(f"⚠️ 섀도우 모니터링 중 에러: {se}")

            # --- 4. 실전(Live) 포지션 관리 로직 ---
            if position is None:
                if last['Long_Signal'] or last['Short_Signal']:
                    pos_type = "LONG" if last['Long_Signal'] else "SHORT"
                    balance = fetch_real_balance()
                    amount = (balance * LEVERAGE) / current_price
                    
                    # [DB 기록] 포지션 진입 정보 저장
                    new_pos = ActivePosition(
                        pos_type=pos_type, entry_time=datetime.now(KST),
                        entry_price=current_price, amount=amount, margin=balance
                    )
                    db.add(new_pos); db.commit()
                    
                    position = {'id': new_pos.id, 'type': pos_type, 'entry_price': current_price, 'amount': amount, 'entry_time': datetime.now(KST)}
                    await send_telegram_msg(f"🎯 [실전 진입] {pos_type}\n💰 가격: {current_price:.2f} USDT")
            
            else:
                roe = ((current_price - position['entry_price']) / position['entry_price'] * LEVERAGE 
                       if position['type'] == "LONG" else 
                       (position['entry_price'] - current_price) / position['entry_price'] * LEVERAGE)

                if roe >= TARGET_ROE or roe <= STOPLOSS_ROE:
                    reason = "익절(TP)" if roe > 0 else "손절(SL)"
                    
                    # [DB 기록] 매매 이력 저장 및 현재 포지션 삭제
                    history = TradeHistory(
                        entry_time=position['entry_time'], exit_time=datetime.now(KST),
                        pos_type=position['type'], entry_price=position['entry_price'],
                        exit_price=current_price, roe_pct=roe*100, exit_reason=reason
                    )
                    db.add(history)
                    db.query(ActivePosition).filter(ActivePosition.id == position['id']).delete()
                    db.commit()
                    
                    await send_telegram_msg(f"🏁 [실전 청산] {reason}\n📈 ROE: {roe*100:.2f}%")
                    position = None

            # 3분 주기 슬립 (캔들 마감 동기화)
            now = datetime.now(KST)
            next_run = now.replace(second=2, microsecond=0) + timedelta(minutes=3 - (now.minute % 3))
            await asyncio.sleep((next_run - now).total_seconds())
            
        except Exception as e:
            logger.error(f"⚠️ 시스템 루프 에러: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_bot())