import os
import shutil
import asyncio
import logging
import sys
import ccxt  # 🌟 실시간 가격 조회를 위한 공용 API 활용
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# 🌟 경로 설정: 상위 폴더(src)를 인식하여 패키지들을 찾을 수 있게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 필수 모듈 임포트
try:
    from core.db_manager import SessionLocal, ActivePosition
    from core.trader import get_exchange
    from research.evolve import generate_and_correct_strategy, run_backtest_and_chart
except ImportError:
    # 실행 환경에 따른 2차 경로 방어
    from src.core.db_manager import SessionLocal, ActivePosition
    from src.core.trader import get_exchange
    from src.research.evolve import generate_and_correct_strategy, run_backtest_and_chart

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 🌟 전역 변수 설정 (NameError 방지 및 레버리지 고정)
STRAT_DIR = "src/strategies"
REPORT_DIR = "data/reports"
LEVERAGE = 10  # 10배 레버리지 설정

logger = logging.getLogger("AdminBot")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start 명령어: 비서 메뉴 안내"""
    if str(update.effective_chat.id) != str(CHAT_ID): return

    welcome_msg = (
        "안녕하세요 보스! Bottom-Scanner 관리 비서입니다. 🤖\n\n"
        "👉 /status : 현재 포지션 및 실시간 수익률 확인\n"
        "👉 /evolve : AI에게 새로운 전략 진화 명령\n"
        "👉 /report : 최근 생성된 후보 전략 리포트 확인\n"
        "👉 /start  : 메뉴 안내 다시 보기"
    )
    await update.message.reply_text(welcome_msg)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status 명령어: 현재 포지션 및 실시간 수익률(ROE) 조회"""
    if str(update.effective_chat.id) != str(CHAT_ID): return

    db = SessionLocal()
    try:
        # 1. DB에서 현재 활성화된 포지션 조회
        pos = db.query(ActivePosition).first()
        if not pos:
            await update.message.reply_text("현재 진행 중인 실전 포지션이 없습니다. 📭")
            return

        # 2. 실시간 가격 조회를 위한 거래소 객체 생성
        exchange = get_exchange()
        
        # 🌟 API 키가 없는 경우, 공용(Public) API로 전환하여 가격만 가져옴
        if not exchange:
            logger.info("🔒 API 키 미설정으로 공용 API 모드로 가격을 조회합니다.")
            exchange = ccxt.binance({'enableRateLimit': True})
            
        # 실시간 가격(Ticker) 가져오기 (비동기 처리)
        ticker = await asyncio.to_thread(exchange.fetch_ticker, 'ETH/USDT')
        current_price = ticker['last']

        # 3. 수익률(ROE) 계산 (레버리지 10배 반영)
        roe = ((current_price - pos.entry_price) / pos.entry_price * LEVERAGE 
               if pos.pos_type == "LONG" else (pos.entry_price - current_price) / pos.entry_price * LEVERAGE)
        
        status_msg = (
            f"📊 **실시간 포지션 브리핑**\n\n"
            f"🔹 **타입**: {pos.pos_type}\n"
            f"🔹 **진입가**: {pos.entry_price:,.2f} USDT\n"
            f"🔹 **현재가**: {current_price:,.2f} USDT\n\n"
            f"🔥 **실시간 ROE: {roe*100:.2f}%**\n"
            f"⏰ **진입시간**: {pos.entry_time.strftime('%m/%d %H:%M:%S')}"
        )
        await update.message.reply_text(status_msg, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"상태 조회 중 에러: {e}")
        await update.message.reply_text(f"⚠️ 조회 중 에러 발생: {str(e)}")
    finally:
        db.close()

async def evolve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/evolve 명령어: AI 전략 진화 프로세스 시작"""
    if str(update.effective_chat.id) != str(CHAT_ID): return
    status_msg = await update.message.reply_text("🤖 AI 전략 진화를 시작합니다. (약 1~2분 소요)...")

    try:
        # 🌟 진화 로직 비동기 실행
        new_code = await asyncio.to_thread(generate_and_correct_strategy)
        if new_code:
            res_pct, count = await asyncio.to_thread(run_backtest_and_chart)
            stats_file = f"{REPORT_DIR}/report_stats.txt"
            with open(stats_file, "w") as f:
                f.write(f"{res_pct:.2f},{count}")
            
            await status_msg.edit_text(f"🎉 진화 성공!\n📈 수익률: {res_pct:.2f}% | 거래: {count}회")
            await send_report_command(update, context)
        else:
            await status_msg.edit_text("❌ 유효한 전략 생성에 실패했습니다.")
    except Exception as e:
        await status_msg.edit_text(f"⚠️ 에러 발생: {str(e)}")

async def send_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/report 명령어: 리포트 차트와 결재 버튼 전송"""
    if str(update.effective_chat.id) != str(CHAT_ID): return 
    report_image = f"{REPORT_DIR}/report.png"
    candidate_file = f"{STRAT_DIR}/strategy_candidate.py"

    if not os.path.exists(report_image) or not os.path.exists(candidate_file):
        await update.message.reply_text("📦 대기 중인 후보 전략이 없습니다. /evolve를 먼저 실행하세요.")
        return

    keyboard = [
        [InlineKeyboardButton("🚀 실전 Live 투입", callback_data="DEPLOY_LIVE")],
        [InlineKeyboardButton("👻 섀도우 모드 투입", callback_data="DEPLOY_SHADOW")],
        [InlineKeyboardButton("⏪ 이전 코드로 롤백", callback_data="ROLLBACK")],
        [InlineKeyboardButton("❌ 반려 및 삭제", callback_data="REJECT")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    with open(report_image, "rb") as photo:
        await context.bot.send_photo(
            chat_id=CHAT_ID, 
            photo=photo, 
            caption="🤖 **AI 전략 개선 제안서**\n보스, 위 전략을 실전에 반영할까요?",
            reply_markup=reply_markup
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """버튼 클릭 처리 로직"""
    query = update.callback_query
    if str(update.effective_chat.id) != str(CHAT_ID): return
    await query.answer() 
    
    live_strat = f"{STRAT_DIR}/strategy.py"
    backup_strat = f"{STRAT_DIR}/strategy_backup.py"
    candidate_strat = f"{STRAT_DIR}/strategy_candidate.py"
    shadow_strat = f"{STRAT_DIR}/strategy_shadow.py"
    
    try:
        if query.data == "DEPLOY_LIVE":
            shutil.copyfile(live_strat, backup_strat)
            shutil.copyfile(candidate_strat, live_strat)
            await query.edit_message_caption("✅ **결재 승인** 실전 전략이 교체되었습니다.")
        elif query.data == "DEPLOY_SHADOW":
            shutil.copyfile(candidate_strat, shadow_strat)
            await query.edit_message_caption("👻 **섀도우 가동** 검증 모드에서 성과를 추적합니다.")
        elif query.data == "ROLLBACK":
            if os.path.exists(backup_strat):
                shutil.copyfile(backup_strat, live_strat)
                await query.edit_message_caption("⏪ **롤백 완료** 이전 버전으로 복구되었습니다.")
            else:
                await query.edit_message_caption("⚠️ 백업 파일이 없습니다.")
        elif query.data == "REJECT":
            if os.path.exists(candidate_strat): os.remove(candidate_strat)
            await query.edit_message_caption("❌ **반려** 후보 전략이 삭제되었습니다.")
    except Exception as e:
        await query.edit_message_caption(f"⚠️ 처리 중 오류: {str(e)}")

if __name__ == "__main__":
    # 필수 폴더 생성
    os.makedirs(STRAT_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("report", send_report_command))
    app.add_handler(CommandHandler("evolve", evolve_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("👔 Bottom-Scanner 관리 비서 가동 중 (실시간 가격 조회 지원)...")
    app.run_polling()