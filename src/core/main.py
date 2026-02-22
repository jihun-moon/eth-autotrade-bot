import os
import asyncio
import logging
import importlib
import traceback
from datetime import datetime, timedelta, timezone
from telegram import Bot
from dotenv import load_dotenv

from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
from utils.ai_analyzer import analyze_market_with_ai
import strategies.strategy as strategy 
from core.db_manager import init_db, SessionLocal, ActivePosition, TradeHistory
from core.trader import fetch_real_balance, execute_order 

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
                    handlers=[logging.FileHandler("data/reports/bot.log"), logging.StreamHandler()])
logger = logging.getLogger("BottomScanner")

load_dotenv()
TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_TOKEN'), os.getenv('TELEGRAM_CHAT_ID')
KST, LEVERAGE = timezone(timedelta(hours=9)), 10

async def send_telegram_msg(message):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"[Bottom-Scanner]\n{message}", parse_mode='Markdown')
    except: logger.error("❌ 알림 실패")

async def run_bot():
    init_db(); db = SessionLocal()
    last_analysis_hour = -1 
    saved_pos = db.query(ActivePosition).first()
    position = None
    if saved_pos:
        position = {'id': saved_pos.id, 'type': saved_pos.pos_type, 'entry_price': saved_pos.entry_price,
                    'amount': saved_pos.amount, 'tp': saved_pos.tp_pct, 'sl': saved_pos.sl_pct, 'entry_time': saved_pos.entry_time}

    await send_telegram_msg("✅ **시스템 가동 시작!**")

    while True:
        try:
            df_ind = add_indicators(fetch_historical_data(limit=2000))
            current_time = datetime.now(KST)

            # 정기 AI 분석 보고
            if current_time.hour != last_analysis_hour:
                analysis = await analyze_market_with_ai(df_ind)
                await send_telegram_msg(f"🧠 **정기 시장 분석**\n\n{analysis}")
                last_analysis_hour = current_time.hour

            importlib.reload(strategy)
            df, d_params = strategy.apply_strategy(df_ind.copy())
            last = df.iloc[-1]
            current_price = last['close']

            if position is None:
                if last.get('Long_Signal') or last.get('Short_Signal'):
                    pos_type = "LONG" if last['Long_Signal'] else "SHORT"
                    balance = fetch_real_balance()
                    amount = (balance * LEVERAGE) / current_price
                    if await execute_order(pos_type, amount):
                        new_pos = ActivePosition(pos_type=pos_type, entry_time=datetime.now(KST), entry_price=current_price, 
                                                 amount=amount, margin=balance, tp_pct=d_params['tp'], sl_pct=d_params['sl'])
                        db.add(new_pos); db.commit(); db.refresh(new_pos)
                        position = {'id': new_pos.id, 'type': pos_type, 'entry_price': current_price, 'amount': amount, 
                                    'tp': d_params['tp'], 'sl': d_params['sl'], 'entry_time': datetime.now(KST)}
                        await send_telegram_msg(f"🎯 [실전 진입] {pos_type} @ {current_price}")
            else:
                roe = ((current_price - position['entry_price']) / position['entry_price'] * LEVERAGE 
                       if position['type']=="LONG" else (position['entry_price'] - current_price) / position['entry_price'] * LEVERAGE)
                if roe >= (position['tp'] * LEVERAGE) or roe <= -(position['sl'] * LEVERAGE):
                    if await execute_order('EXIT', position['amount']):
                        db.query(ActivePosition).filter(ActivePosition.id == position['id']).delete(); db.commit()
                        await send_telegram_msg(f"🏁 [청산 완료] ROE: {roe*100:.2f}%")
                        position = None

            now = datetime.now(KST)
            next_run = now.replace(second=5, microsecond=0) + timedelta(minutes=3 - (now.minute % 3))
            wait_sec = (next_run - now).total_seconds()
            if wait_sec < 0: wait_sec += 180 
            await asyncio.sleep(max(wait_sec, 5))
            
        except Exception as e:
            err = traceback.format_exc()
            await send_telegram_msg(f"🚨 **에러 발생!**\n`{str(e)}`\n\n🤖 AI가 분석 및 자가 치유를 위해 /evolve 실행을 권장합니다.")
            db.rollback(); await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(run_bot())