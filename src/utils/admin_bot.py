import os
import shutil
import asyncio
import logging
import sys
import ccxt
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db_manager import SessionLocal, ActivePosition
from core.trader import get_exchange
from research.evolve import generate_and_correct_strategy, run_backtest_and_chart
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
from utils.ai_analyzer import analyze_market_with_ai

load_dotenv()
TELEGRAM_TOKEN, CHAT_ID = os.getenv('TELEGRAM_TOKEN'), os.getenv('TELEGRAM_CHAT_ID')
STRAT_DIR, REPORT_DIR, LEVERAGE = "src/strategies", "data/reports", 10

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(CHAT_ID): return
    status_msg = await update.message.reply_text("🧐 보스, AI가 차트 분석 중입니다...")
    try:
        df = add_indicators(fetch_historical_data(limit=1000))
        analysis = await analyze_market_with_ai(df, update.message.text)
        await status_msg.edit_text(f"🧠 **AI 실시간 분석**\n\n{analysis}", parse_mode='Markdown')
    except Exception as e: await status_msg.edit_text(f"⚠️ 에러: {str(e)}")

async def start_command(update, context):
    await update.message.reply_text("🤖 **AI 에이전트 가동 중**\n질문을 입력하시거나 명령어를 사용하세요.\n/status, /evolve, /report")

async def status_command(update, context):
    db = SessionLocal()
    pos = db.query(ActivePosition).first()
    if not pos: await update.message.reply_text("포지션 없음"); return
    ticker = await asyncio.to_thread(ccxt.binance().fetch_ticker, 'ETH/USDT')
    roe = ((ticker['last'] - pos.entry_price) / pos.entry_price * LEVERAGE if pos.pos_type=="LONG" else (pos.entry_price - ticker['last']) / pos.entry_price * LEVERAGE)
    await update.message.reply_text(f"📊 **포지션 상태**\n타입: {pos.pos_type}\nROE: {roe*100:.2f}%", parse_mode='Markdown')
    db.close()

async def evolve_command(update, context):
    await update.message.reply_text("🤖 AI 전략 진화 시작...")
    if generate_and_correct_strategy():
        pct, count = run_backtest_and_chart()
        await update.message.reply_text(f"🎉 성공! 수익률: {pct:.2f}% / 거래: {count}회")
        await send_report_command(update, context)

async def send_report_command(update, context):
    report_path = os.path.join(REPORT_DIR, "report.png")
    keyboard = [[InlineKeyboardButton("🚀 실전 투입", callback_data="DEPLOY_LIVE"), InlineKeyboardButton("👻 섀도우", callback_data="DEPLOY_SHADOW")]]
    with open(report_path, "rb") as p: await context.bot.send_photo(CHAT_ID, photo=p, caption="🤖 **AI 승인 요청**", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update, context):
    query = update.callback_query; await query.answer()
    if query.data == "DEPLOY_LIVE":
        shutil.copyfile("src/strategies/strategy_candidate.py", "src/strategies/strategy.py")
        await query.edit_message_caption("✅ 실전 투입 완료!")

if __name__ == "__main__":
    os.makedirs(STRAT_DIR, exist_ok=True); os.makedirs(REPORT_DIR, exist_ok=True)
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("evolve", evolve_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling()