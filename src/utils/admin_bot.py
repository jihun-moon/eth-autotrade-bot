import os
import shutil
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# AI 진화 엔진 임포트
from research.evolve import generate_and_correct_strategy, run_backtest_and_chart

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# [경로 설정] MLOps 표준 구조 반영
STRAT_DIR = "src/strategies"
REPORT_DIR = "data/reports"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start 명령어 안내"""
    user_chat_id = str(update.effective_chat.id)
    if user_chat_id != str(CHAT_ID): return

    welcome_msg = (
        "안녕하세요 보스! Bottom-Scanner 비서입니다. 🤖\n\n"
        "👉 /evolve : AI에게 새로운 전략 진화 명령\n"
        "👉 /report : 대기 중인 후보 전략 결재 요청\n"
        "👉 /start  : 안내 메시지 보기"
    )
    await update.message.reply_text(welcome_msg)

async def evolve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/evolve 명령어: AI 전략 진화 프로세스 시작"""
    user_chat_id = str(update.effective_chat.id)
    if user_chat_id != str(CHAT_ID): return

    await update.message.reply_text("🤖 AI가 시장 데이터를 분석하여 전략 진화를 시작합니다...\n(약 1~2분 소요. 완료 후 리포트를 보낼게요!)")

    try:
        # 진화 로직 비동기 실행
        new_code = await asyncio.to_thread(generate_and_correct_strategy)
        
        if new_code:
            res_pct, count = await asyncio.to_thread(run_backtest_and_chart)
            
            # 통계 정보 저장
            stats_file = f"{REPORT_DIR}/report_stats.txt"
            with open(stats_file, "w") as f:
                f.write(f"{res_pct:.2f},{count}")
            
            await update.message.reply_text(f"🎉 전략 진화 성공! (수익률: {res_pct:.2f}%)")
            
            # 자동으로 리포트 결재창 호출
            await send_report_command(update, context)
        else:
            await update.message.reply_text("❌ AI가 전략 생성에 실패했습니다.")
            
    except Exception as e:
        await update.message.reply_text(f"⚠️ 진화 중 에러 발생: {e}")

async def send_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/report 명령어: 리포트 및 버튼 전송"""
    user_chat_id = str(update.effective_chat.id)
    if user_chat_id != str(CHAT_ID): return 

    report_image = f"{REPORT_DIR}/report.png"
    report_stats = f"{REPORT_DIR}/report_stats.txt"
    candidate_file = f"{STRAT_DIR}/strategy_candidate.py"

    if not os.path.exists(report_image) or not os.path.exists(candidate_file):
        await update.message.reply_text("대기 중인 후보 전략이 없습니다. /evolve를 먼저 실행하세요.")
        return

    with open(report_stats, "r") as f:
        stats = f.read().split(',')
        return_pct = stats[0]

    # [수정] 롤백 버튼 다시 추가됨
    keyboard = [
        [InlineKeyboardButton("🚀 실전 Live 투입", callback_data="DEPLOY_LIVE")],
        [InlineKeyboardButton("👻 섀도우 모드 투입", callback_data="DEPLOY_SHADOW")],
        [InlineKeyboardButton("⏪ 이전 코드로 롤백", callback_data="ROLLBACK")],
        [InlineKeyboardButton("❌ 반려 (삭제)", callback_data="REJECT")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    with open(report_image, "rb") as photo:
        await context.bot.send_photo(
            chat_id=CHAT_ID,
            photo=photo,
            caption=f"🤖 **[AI 전략 개선 제안서]**\n\n📈 백테스트 수익률: {return_pct}%\n보스, 어떻게 처리할까요?",
            reply_markup=reply_markup
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """버튼 클릭 처리"""
    query = update.callback_query
    if str(update.effective_chat.id) != str(CHAT_ID):
        await query.answer("권한이 없습니다.")
        return

    await query.answer() 
    
    live_strat = f"{STRAT_DIR}/strategy.py"
    backup_strat = f"{STRAT_DIR}/strategy_backup.py"
    candidate_strat = f"{STRAT_DIR}/strategy_candidate.py"
    shadow_strat = f"{STRAT_DIR}/strategy_shadow.py"
    
    if query.data == "DEPLOY_LIVE":
        shutil.copyfile(live_strat, backup_strat)
        shutil.copyfile(candidate_strat, live_strat)
        await query.edit_message_caption("✅ 실전 투입 완료! 전략이 즉시 교체되었습니다.")
        
    elif query.data == "DEPLOY_SHADOW":
        shutil.copyfile(candidate_strat, shadow_strat)
        await query.edit_message_caption("👻 섀도우 가동! 성과를 추적합니다.")

    elif query.data == "ROLLBACK":
        # 롤백 로직 실행
        if os.path.exists(backup_strat):
            shutil.copyfile(backup_strat, live_strat)
            await query.edit_message_caption("⏪ 롤백 완료! 이전 버전으로 복구되었습니다.")
        else:
            await query.edit_message_caption("⚠️ 백업 파일이 없습니다.")
            
    elif query.data == "REJECT":
        if os.path.exists(candidate_strat):
            os.remove(candidate_strat)
        await query.edit_message_caption("❌ 반려되었습니다.")

if __name__ == "__main__":
    os.makedirs(STRAT_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("report", send_report_command))
    app.add_handler(CommandHandler("evolve", evolve_command))
    
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("👔 Bottom-Scanner 관리 비서 가동 중...")
    app.run_polling()