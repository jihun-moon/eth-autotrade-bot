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

# 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db_manager import SessionLocal, ActivePosition
from research.evolve import generate_and_correct_strategy, run_backtest_and_chart
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
from utils.ai_analyzer import analyze_market_with_ai

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

STRAT_DIR, REPORT_DIR, LEVERAGE = "src/strategies", "data/reports", 10

async def start_command(update, context):
    if str(update.effective_chat.id) != str(CHAT_ID): return
    msg = (
        "👋 **안녕하세요 보스! AI 에이전트 가동 중입니다.**\n\n"
        "💬 **대화형 분석**: 궁금한 것을 그냥 물어보세요!\n"
        "   (예: '지금 롱 타도 돼?', '현재 매물대 어때?')\n\n"
        "⚙️ **관리 명령어**\n"
        "🔹 /status : 현재 포지션 수익률 확인\n"
        "🔹 /evolve : AI 전략 자가 학습 시작\n"
        "🔹 /report : 최근 분석 리포트(차트) 확인"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def handle_chat(update, context):
    """일상 대화와 분석을 스스로 구분하는 핸들러"""
    if str(update.effective_chat.id) != str(CHAT_ID): return
    status_msg = await update.message.reply_text("🤔 **생각 중...**")
    try:
        df = add_indicators(fetch_historical_data(limit=1000))
        response = await analyze_market_with_ai(df, update.message.text)
        await status_msg.edit_text(response, parse_mode='Markdown')
    except Exception as e:
        await status_msg.edit_text(f"❌ **에러**: {str(e)}")

async def status_command(update, context):
    db = SessionLocal()
    pos = db.query(ActivePosition).first()
    if not pos:
        await update.message.reply_text("📭 **보유 중인 포지션이 없습니다.**")
        return
    ticker = await asyncio.to_thread(ccxt.binance().fetch_ticker, 'ETH/USDT')
    roe = ((ticker['last'] - pos.entry_price) / pos.entry_price * LEVERAGE if pos.pos_type == "LONG" else (pos.entry_price - ticker['last']) / pos.entry_price * LEVERAGE)
    msg = (
        f"📊 **실시간 포지션 브리핑**\n"
        f"━━━━━━━━━━━━━━\n"
        f"🔹 **타입**: `{pos.pos_type}` ({LEVERAGE}x)\n"
        f"🔹 **진입가**: `{pos.entry_price:,.2f} USDT`\n"
        f"🔹 **현재가**: `{ticker['last']:,.2f} USDT`\n"
        f"🔥 **실시간 ROE**: `{roe*100:+.2f}%`"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')
    db.close()

async def evolve_command(update, context):
    msg = await update.message.reply_text("🤖 **AI가 시장을 학습하며 코드를 수정 중입니다...**")
    if generate_and_correct_strategy():
        pct, count = run_backtest_and_chart()
        await msg.edit_text(f"🎉 **진화 성공!**\n📈 **수익률**: `{pct:.2f}%` | **거래**: `{count}회`")
        await send_report_command(update, context)

async def send_report_command(update, context):
    path = f"{REPORT_DIR}/report.png"
    if os.path.exists(path):
        kb = [[InlineKeyboardButton("🚀 실전 투입", callback_data="DEPLOY_LIVE")]]
        with open(path, "rb") as f:
            await context.bot.send_photo(CHAT_ID, photo=f, caption="🤖 **AI 개선 전략 승인 요청**", reply_markup=InlineKeyboardMarkup(kb))

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "DEPLOY_LIVE":
        shutil.copyfile(f"{STRAT_DIR}/strategy_candidate.py", f"{STRAT_DIR}/strategy.py")
        await query.edit_message_caption("✅ **실전 투입 완료!**")

if __name__ == "__main__":
    os.makedirs(STRAT_DIR, exist_ok=True); os.makedirs(REPORT_DIR, exist_ok=True)
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("evolve", evolve_command))
    app.add_handler(CommandHandler("report", send_report_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling()