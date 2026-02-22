import os
import shutil
import asyncio
import logging
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# AI 진화 엔진 임포트
from research.evolve import generate_and_correct_strategy, run_backtest_and_chart

# 1. 로깅 설정 (Docker에서 실시간으로 확인 가능하도록)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("AdminBot")

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# [경로 설정] Docker 환경에 맞게 절대 경로 권장
STRAT_DIR = "src/strategies"
REPORT_DIR = "data/reports"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start 명령어 안내"""
    if str(update.effective_chat.id) != str(CHAT_ID): return
    welcome_msg = (
        "안녕하세요 보스! Bottom-Scanner 비서입니다. 🤖\n\n"
        "👉 /evolve : AI에게 새로운 전략 진화 명령 (ATR 동적 로직 적용)\n"
        "👉 /report : 최근 생성된 후보 전략 리포트 보기\n"
        "👉 /start  : 안내 메시지 보기"
    )
    await update.message.reply_text(welcome_msg)

async def evolve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/evolve 명령어: AI 전략 진화 프로세스 시작"""
    if str(update.effective_chat.id) != str(CHAT_ID): return

    await update.message.reply_text("🤖 AI가 시장 데이터 및 변동성(ATR)을 분석 중입니다...\n(약 1~2분 소요. 완료 후 리포트를 보낼게요!)")
    logger.info("🚀 AI 전략 진화 프로세스 시작됨...")

    try:
        # 1. AI 코드 생성 및 자가 수선 (비동기 스레드 실행)
        new_code = await asyncio.to_thread(generate_and_correct_strategy)
        
        if new_code:
            logger.info("✅ AI 전략 코드 생성 완료. 백테스트 시작...")
            # 2. 백테스트 및 차트 생성 (ATR 컬럼 기반 로직 적용)
            res_pct, count = await asyncio.to_thread(run_backtest_and_chart)
            
            # 통계 정보 저장
            stats_file = os.path.join(REPORT_DIR, "report_stats.txt")
            with open(stats_file, "w") as f:
                f.write(f"{res_pct:.2f},{count}")
            
            logger.info(f"📊 백테스트 완료: 수익률 {res_pct:.2f}%, 거래 횟수 {count}회")
            await update.message.reply_text(f"🎉 전략 진화 성공!\n📈 백테스트 수익률: {res_pct:.2f}%")
            
            # 자동으로 리포트 결재창 호출
            await send_report_command(update, context)
        else:
            logger.warning("❌ AI가 유효한 전략 코드를 생성하지 못함")
            await update.message.reply_text("❌ AI가 전략 생성 및 문법 검증에 실패했습니다. 다시 시도해 주세요.")
            
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"⚠️ 진화 중 치명적 에러 발생:\n{error_trace}")
        await update.message.reply_text(f"⚠️ 시스템 오류 발생:\n{str(e)}")

async def send_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/report 명령어: 리포트 이미지 및 승인 버튼 전송"""
    if str(update.effective_chat.id) != str(CHAT_ID): return 

    report_image = os.path.join(REPORT_DIR, "report.png")
    report_stats = os.path.join(REPORT_DIR, "report_stats.txt")
    candidate_file = os.path.join(STRAT_DIR, "strategy_candidate.py")

    if not os.path.exists(report_image) or not os.path.exists(candidate_file):
        await update.message.reply_text("대기 중인 후보 전략이 없습니다. /evolve를 먼저 실행하세요.")
        return

    try:
        with open(report_stats, "r") as f:
            stats = f.read().split(',')
            return_pct = stats[0]
            trade_count = stats[1] if len(stats) > 1 else "N/A"

        keyboard = [
            [InlineKeyboardButton("🚀 실전 Live 투입 (즉시 교체)", callback_data="DEPLOY_LIVE")],
            [InlineKeyboardButton("👻 섀도우 모드 투입 (검증)", callback_data="DEPLOY_SHADOW")],
            [InlineKeyboardButton("⏪ 이전 코드로 롤백", callback_data="ROLLBACK")],
            [InlineKeyboardButton("❌ 반려 (삭제)", callback_data="REJECT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        with open(report_image, "rb") as photo:
            caption = (
                f"🤖 **[AI 전략 개선 리포트]**\n\n"
                f"📈 예상 수익률: {return_pct}%\n"
                f"🔢 총 거래 횟수: {trade_count}회\n"
                f"💡 특이사항: ATR 동적 TP/SL 적용 완료\n\n"
                f"보스, 이 전략을 실전에 투입할까요?"
            )
            await context.bot.send_photo(
                chat_id=CHAT_ID,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"❌ 리포트 전송 실패: {e}")
        await update.message.reply_text("리포트 파일을 읽는 중 에러가 발생했습니다.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """버튼 클릭 시 파일 조작 및 배포 처리"""
    query = update.callback_query
    if str(update.effective_chat.id) != str(CHAT_ID): return

    await query.answer() 
    
    live_strat = os.path.join(STRAT_DIR, "strategy.py")
    backup_strat = os.path.join(STRAT_DIR, "strategy_backup.py")
    candidate_strat = os.path.join(STRAT_DIR, "strategy_candidate.py")
    shadow_strat = os.path.join(STRAT_DIR, "strategy_shadow.py")
    
    try:
        if query.data == "DEPLOY_LIVE":
            # 1. 기존 파일을 백업하고 새로운 후보로 교체
            if os.path.exists(live_strat):
                shutil.copyfile(live_strat, backup_strat)
            shutil.copyfile(candidate_strat, live_strat)
            logger.info("✅ [DEPLOY] Candidate 전략이 실전(Live)에 배포되었습니다.")
            await query.edit_message_caption("✅ 실전 투입 완료! 전략이 즉시 교체되었습니다. (기존 버전 백업됨)")
            
        elif query.data == "DEPLOY_SHADOW":
            shutil.copyfile(candidate_strat, shadow_strat)
            logger.info("✅ [SHADOW] Candidate 전략이 섀도우 모드에 배포되었습니다.")
            await query.edit_message_caption("👻 섀도우 가동! 이제부터 가상 수익률을 추적합니다.")

        elif query.data == "ROLLBACK":
            if os.path.exists(backup_strat):
                shutil.copyfile(backup_strat, live_strat)
                logger.info("⏪ [ROLLBACK] 이전 백업 버전으로 복구되었습니다.")
                await query.edit_message_caption("⏪ 롤백 완료! 이전 안정 버전으로 복구되었습니다.")
            else:
                await query.edit_message_caption("⚠️ 백업 파일이 없습니다. 롤백이 불가능합니다.")
                
        elif query.data == "REJECT":
            if os.path.exists(candidate_strat):
                os.remove(candidate_strat)
            logger.info("❌ [REJECT] 후보 전략이 반려 및 삭제되었습니다.")
            await query.edit_message_caption("❌ 반려되었습니다. 후보 파일이 삭제되었습니다.")

    except Exception as e:
        logger.error(f"❌ 배포 처리 중 에러: {e}")
        await query.edit_message_caption(f"⚠️ 처리 중 오류 발생: {e}")

if __name__ == "__main__":
    os.makedirs(STRAT_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("report", send_report_command))
    app.add_handler(CommandHandler("evolve", evolve_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("👔 Bottom-Scanner 관리 비서 가동 시작 (Polling...)")
    app.run_polling()