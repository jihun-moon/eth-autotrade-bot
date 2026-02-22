import os
import asyncio
import logging
import importlib
from datetime import datetime, timedelta, timezone
from telegram import Bot
from dotenv import load_dotenv

# 경로 설정 및 유틸리티 임포트
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
import strategies.strategy as strategy 
from core.db_manager import init_db, SessionLocal, ActivePosition, TradeHistory
from core.trader import fetch_real_balance, execute_order 

# 로깅 설정 (안정화 버전 + 파일 기록)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
                    handlers=[logging.FileHandler("data/reports/bot.log"), logging.StreamHandler()])
logger = logging.getLogger("BottomScanner")

load_dotenv()
TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_TOKEN'), os.getenv('TELEGRAM_CHAT_ID')
KST, LEVERAGE = timezone(timedelta(hours=9)), 10

async def send_telegram_msg(message):
    """텔레그램 메시지 전송"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"[Bottom-Scanner]\n{message}")
    except Exception as e: 
        logger.error(f"❌ 알림 실패: {e}")

async def heartbeat_loop():
    """시스템 가동 상태 주기적 보고 (1시간 단위)"""
    while True:
        try:
            await send_telegram_msg(f"💓 [Heartbeat] 가동 중\n⏰ {datetime.now(KST).strftime('%H:%M:%S')}")
            await asyncio.sleep(3600)
        except: 
            await asyncio.sleep(60)

async def run_bot():
    """실전 매매 메인 루프"""
    init_db(); db = SessionLocal()
    asyncio.create_task(heartbeat_loop())
    
    # 🌟 1. 기존 포지션 복구 (DB 기반 - 깃허브 기능)
    saved_pos = db.query(ActivePosition).first()
    position = None
    if saved_pos:
        position = {
            'id': saved_pos.id, 'type': saved_pos.pos_type, 'entry_price': saved_pos.entry_price,
            'amount': saved_pos.amount, 'tp': saved_pos.tp_pct, 'sl': saved_pos.sl_pct, 
            'entry_time': saved_pos.entry_time
        }
        logger.info(f"♻️ 포지션 복구 완료: {position['type']} (진입가: {position['entry_price']})")

    shadow_position = None
    await send_telegram_msg("✅ Bottom-Scanner 시스템 가동 시작!")

    while True:
        try:
            # 🌟 2. 데이터 수집 및 지표 계산 (안정화 버전 로직)
            raw_data = fetch_historical_data(limit=2000)
            if raw_data is None or len(raw_data) < 500:
                logger.warning("⚠️ 데이터 부족으로 대기 중...")
                await asyncio.sleep(60)
                continue

            # 지표 계산 및 전략 파일 리로드
            df_ind = add_indicators(raw_data)
            importlib.reload(strategy)
            
            # 전략 적용
            res = strategy.apply_strategy(df_ind.copy())
            df, d_params = res if isinstance(res, tuple) else (res, {'tp': 0.02, 'sl': 0.015})
            last = df.iloc[-1]
            current_price = last['close']

            # ── 3. 섀도우 모드 감시 (AI 후보 전략 테스트 - 깃허브 기능) ──
            shadow_path = "src/strategies/strategy_shadow.py"
            if os.path.exists(shadow_path):
                try:
                    import strategies.strategy_shadow as s_shadow
                    importlib.reload(s_shadow)
                    res_s = s_shadow.apply_strategy(df_ind.copy())
                    df_s, s_params = res_s if isinstance(res_s, tuple) else (res_s, {'tp': 0.02, 'sl': 0.015})
                    l_s = df_s.iloc[-1]
                    
                    if shadow_position is None:
                        if l_s.get('Long_Signal') or l_s.get('Short_Signal'):
                            shadow_position = {
                                'type': "LONG" if l_s['Long_Signal'] else "SHORT", 
                                'price': l_s['close'],
                                'tp': s_params.get('tp', 0.02),
                                'sl': s_params.get('sl', 0.015)
                            }
                            await send_telegram_msg(f"👻 [섀도우 진입] {shadow_position['type']} @ {shadow_position['price']}")
                    else:
                        s_roe = ((current_price - shadow_position['price']) / shadow_position['price'] * LEVERAGE 
                                 if shadow_position['type']=="LONG" else (shadow_position['price'] - current_price) / shadow_position['price'] * LEVERAGE)
                        
                        if s_roe >= (shadow_position['tp'] * LEVERAGE) or s_roe <= -(shadow_position['sl'] * LEVERAGE):
                            await send_telegram_msg(f"👻 [섀도우 종료] 수익률: {s_roe*100:.2f}%")
                            shadow_position = None
                except Exception as shadow_e:
                    logger.error(f"⚠️ 섀도우 모드 에러: {shadow_e}")

            # ── 4. 실전 포지션 관리 (안정화 버전 계산식 + DB 연동) ──
            if position is None:
                if last.get('Long_Signal') or last.get('Short_Signal'):
                    pos_type = "LONG" if last['Long_Signal'] else "SHORT"
                    
                    # 실제 거래소 잔고 조회 및 주문 수량 계산
                    balance = fetch_real_balance()
                    amount = (balance * LEVERAGE) / current_price
                    order_res = await execute_order(pos_type, amount)
                    
                    if order_res:
                        new_pos = ActivePosition(pos_type=pos_type, entry_time=datetime.now(KST), entry_price=current_price, 
                                                 amount=amount, margin=balance, tp_pct=d_params['tp'], sl_pct=d_params['sl'])
                        db.add(new_pos); db.commit(); db.refresh(new_pos)
                        
                        position = {
                            'id': new_pos.id, 'type': pos_type, 'entry_price': current_price, 'amount': amount, 
                            'tp': d_params['tp'], 'sl': d_params['sl'], 'entry_time': datetime.now(KST)
                        }
                        await send_telegram_msg(f"🎯 [실전 진입] {pos_type}\n💰 진입가: {current_price}\n📈 목표: {d_params['tp']*100:.1f}%")
                else:
                    logger.info(f"🔍 [감시 중] 가격: {current_price:.2f} | 진입 대기...")
            else:
                roe = ((current_price - position['entry_price']) / position['entry_price'] * LEVERAGE 
                       if position['type']=="LONG" else (position['entry_price'] - current_price) / position['entry_price'] * LEVERAGE)
                
                if roe >= (position['tp'] * LEVERAGE) or roe <= -(position['sl'] * LEVERAGE):
                    exit_res = await execute_order('EXIT', position['amount'])
                    
                    if exit_res:
                        reason = "익절" if roe > 0 else "손절"
                        db.add(TradeHistory(entry_time=position['entry_time'], exit_time=datetime.now(KST), pos_type=position['type'], 
                                            entry_price=position['entry_price'], exit_price=current_price, roe_pct=roe*100, exit_reason=reason))
                        db.query(ActivePosition).filter(ActivePosition.id == position['id']).delete(); db.commit()
                        await send_telegram_msg(f"🏁 [실전 청산] {reason}\n📊 최종 ROE: {roe*100:.2f}%")
                        position = None

            # 🌟 5. 정밀 대기 로직 (안정화 버전의 핵심 - Drift 방지)
            now = datetime.now(KST)
            next_run = now.replace(second=5, microsecond=0) + timedelta(minutes=3 - (now.minute % 3))
            wait_sec = (next_run - now).total_seconds()
            if wait_sec < 0: wait_sec += 180 
            
            logger.info(f"⏳ 다음 분석까지 {wait_sec:.1f}초 정밀 대기...")
            await asyncio.sleep(max(wait_sec, 10))
            
        except Exception as e:
            logger.error(f"⚠️ 메인 루프 치명적 에러: {e}")
            db.rollback() 
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(run_bot())