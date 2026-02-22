import os
import asyncio
import logging
import importlib
from datetime import datetime, timedelta, timezone
from telegram import Bot
from dotenv import load_dotenv

from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
import strategies.strategy as strategy 
from core.db_manager import init_db, SessionLocal, ActivePosition, TradeHistory
from core.trader import fetch_real_balance, execute_order

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("data/reports/bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger("BottomScanner")

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
KST = timezone(timedelta(hours=9))
LEVERAGE = 10

async def send_telegram_msg(message):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"[Bottom-Scanner]\n{message}")
    except Exception as e:
        logger.error(f"❌ 알림 실패: {e}")

async def heartbeat_loop():
    while True:
        try:
            await send_telegram_msg(f"💓 [Heartbeat] 정상 가동 중\n⏰ {datetime.now(KST).strftime('%H:%M:%S')}")
            await asyncio.sleep(3600)
        except: await asyncio.sleep(60)

async def run_bot():
    init_db()
    db = SessionLocal()
    asyncio.create_task(heartbeat_loop())
    
    saved_pos = db.query(ActivePosition).first()
    position = None
    if saved_pos:
        position = {
            'id': saved_pos.id, 'type': saved_pos.pos_type, 'entry_time': saved_pos.entry_time,
            'entry_price': saved_pos.entry_price, 'amount': saved_pos.amount,
            'tp': saved_pos.tp_pct, 'sl': saved_pos.sl_pct
        }
        logger.info(f"♻️ 복구 성공: {position['type']} (TP: {position['tp']*100:.2f}%)")

    shadow_position = None
    await send_telegram_msg("✅ 시스템 가동! (오류 수정 및 복구 엔진 활성)")

    while True:
        try:
            df_ind = add_indicators(fetch_historical_data(limit=1000))
            importlib.reload(strategy)
            
            # [수정] 전략 파일에서 반환하는 두 개의 값을 정확히 받음
            df, d_params = strategy.apply_strategy(df_ind.copy())
            last = df.iloc[-1]
            current_price = last['close']

            # --- 섀도우 로직 ---
            shadow_path = "src/strategies/strategy_shadow.py"
            if os.path.exists(shadow_path):
                import strategies.strategy_shadow as s_shadow
                importlib.reload(s_shadow)
                # 섀도우 전략도 동일하게 두 개를 반환하도록 수정되었다고 가정 (안 되어 있으면 에러 방지용 try-except 필요)
                try:
                    df_s, _ = s_shadow.apply_strategy(df_ind.copy())
                    l_s = df_s.iloc[-1]
                    if shadow_position is None and (l_s.get('Long_Signal') or l_s.get('Short_Signal')):
                        stype = "LONG" if l_s['Long_Signal'] else "SHORT"
                        shadow_position = {'type': stype, 'price': l_s['close']}
                        await send_telegram_msg(f"👻 [섀도우 진입] {stype} 포착")
                    elif shadow_position is not None:
                        s_roe = ((current_price - shadow_position['price']) / shadow_position['price'] * LEVERAGE if shadow_position['type']=="LONG" else (shadow_position['price'] - current_price) / shadow_position['price'] * LEVERAGE)
                        if s_roe >= 0.2 or s_roe <= -0.15:
                            await send_telegram_msg(f"👻 [섀도우 종료] ROE: {s_roe*100:.2f}%")
                            shadow_position = None
                except: pass

            # --- 실전 관리 ---
            if position is None:
                if last['Long_Signal'] or last['Short_Signal']:
                    pos_type = "LONG" if last['Long_Signal'] else "SHORT"
                    balance = fetch_real_balance()
                    amount = (balance * LEVERAGE) / current_price
                    
                    new_pos = ActivePosition(
                        pos_type=pos_type, entry_time=datetime.now(KST),
                        entry_price=current_price, amount=amount, margin=balance,
                        tp_pct=d_params['tp'], sl_pct=d_params['sl']
                    )
                    db.add(new_pos); db.commit(); db.refresh(new_pos)
                    position = {'id': new_pos.id, 'type': pos_type, 'entry_price': current_price, 'amount': amount, 'tp': d_params['tp'], 'sl': d_params['sl'], 'entry_time': datetime.now(KST)}
                    await send_telegram_msg(f"🎯 [실전 진입] {pos_type} | TP: {d_params['tp']*100:.1f}%")
            
            else:
                roe = ((current_price - position['entry_price']) / position['entry_price'] * LEVERAGE if position['type']=="LONG" else (position['entry_price'] - current_price) / position['entry_price'] * LEVERAGE)
                if roe >= (position['tp'] * LEVERAGE) or roe <= -(position['sl'] * LEVERAGE):
                    reason = "익절(TP)" if roe > 0 else "손절(SL)"
                    history = TradeHistory(entry_time=position['entry_time'], exit_time=datetime.now(KST), pos_type=position['type'], entry_price=position['entry_price'], exit_price=current_price, roe_pct=roe*100, exit_reason=reason)
                    db.add(history)
                    db.query(ActivePosition).filter(ActivePosition.id == position['id']).delete()
                    db.commit()
                    await send_telegram_msg(f"🏁 [실전 청산] {reason} | ROE: {roe*100:.2f}%")
                    position = None

            next_run = datetime.now(KST).replace(second=2, microsecond=0) + timedelta(minutes=3 - (datetime.now(KST).minute % 3))
            await asyncio.sleep((next_run - datetime.now(KST)).total_seconds())
        except Exception as e:
            logger.error(f"⚠️ 에러: {e}"); await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_bot())