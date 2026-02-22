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
from core.db_manager import init_db, SessionLocal, ActivePosition
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
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
    except: logger.error("❌ 알림 실패")

async def run_bot():
    init_db(); db = SessionLocal()
    last_analysis_hour = -1
    saved_pos = db.query(ActivePosition).first()
    position = saved_pos if saved_pos else None

    await send_telegram_msg("🚀 **Bottom-Scanner 자동매매 엔진 가동!**")

    while True:
        try:
            # 1. 데이터 및 지표 수집
            raw_data = fetch_historical_data(limit=2000)
            df_ind = add_indicators(raw_data)
            current_time = datetime.now(KST)

            # 2. 정기 AI 분석 보고 (1시간 주기)
            if current_time.hour != last_analysis_hour:
                analysis = await analyze_market_with_ai(df_ind)
                await send_telegram_msg(f"🧠 **AI 정기 분석 보고**\n\n{analysis}")
                last_analysis_hour = current_time.hour

            importlib.reload(strategy)
            df, params = strategy.apply_strategy(df_ind.copy())
            last = df.iloc[-1]

            if position is None:
                if last.get('Long_Signal') or last.get('Short_Signal'):
                    pos_type = "LONG" if last['Long_Signal'] else "SHORT"
                    balance = fetch_real_balance()
                    amount = (balance * LEVERAGE) / last['close']
                    if await execute_order(pos_type, amount):
                        # DB 저장
                        new_pos = ActivePosition(pos_type=pos_type, entry_time=datetime.now(KST), entry_price=last['close'], 
                                                 amount=amount, margin=balance, tp_pct=params['tp'], sl_pct=params['sl'])
                        db.add(new_pos); db.commit(); position = new_pos
                        await send_telegram_msg(f"🎯 **[{pos_type} 진입]** 가격: `{last['close']:,.2f}`")
            else:
                # 수익률 체크 (10배 반영)
                roe = ((last['close'] - position.entry_price) / position.entry_price * LEVERAGE if position.pos_type=="LONG" else (position.entry_price - last['close']) / position.entry_price * LEVERAGE)
                if roe >= (position.tp_pct * LEVERAGE) or roe <= -(position.sl_pct * LEVERAGE):
                    if await execute_order('EXIT', position.amount):
                        db.query(ActivePosition).delete(); db.commit(); position = None
                        await send_telegram_msg(f"🏁 **[포지션 청산]** ROE: `{roe*100:+.2f}%`")

            # 🌟 정밀 대기 (3분 05초 타이밍)
            now = datetime.now(KST)
            next_run = now.replace(second=5, microsecond=0) + timedelta(minutes=3 - (now.minute % 3))
            wait_sec = (next_run - now).total_seconds()
            if wait_sec < 0: wait_sec += 180 
            await asyncio.sleep(max(wait_sec, 10))
            
        except Exception as e:
            await send_telegram_msg(f"🚨 **에러 감지!**\n`{str(e)}`")
            db.rollback(); await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(run_bot())