import os
import shutil
import asyncio
import logging
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# 🌟 경로 설정: 상위 폴더(src)를 인식하여 research 패키지를 찾을 수 있게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# AI 진화 엔진 임포트
try:
    from research.evolve import generate_and_correct_strategy, run_backtest_and_chart
except ImportError:
    # 경로가 다를 경우를 대비한 2차 방어
    from src.research.evolve import generate_and_correct_strategy, run_backtest_and_chart

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# [경로 설정] MLOps 표준 구조 반영
STRAT_DIR = "src/strategies"
REPORT_DIR = "data/reports"

logger = logging.getLogger("AdminBot")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start 명령어 안내"""
    if str(update.effective_chat.id) != str(CHAT_ID): return

    welcome_msg = (
        "안녕하세요 보스! Bottom-Scanner 관리 비서입니다. 🤖\n\n"
        "현재 시스템의 모든 조종간은 보스에게 연결되어 있습니다.\n\n"
        "👉 /evolve : AI에게 새로운 전략 진화 명령 (데이터 분석 + 백테스트)\n"
        "👉 /report : 최근 생성된 후보 전략 리포트 확인 및 결재\n"
        "👉 /start  : 메뉴 안내 다시 보기"
    )
    await update.message.reply_text(welcome_msg)

async def evolve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/evolve 명령어: AI 전략 진화 프로세스 시작"""
    if str(update.effective_chat.id) != str(CHAT_ID): return

    status_msg = await update.message.reply_text("🤖 AI가 시장 데이터를 분석하여 전략 진화를 시작합니다...\n(약 1~2분 소요. 완료 후 리포트를 보낼게요!)")

    try:
        # 🌟 진화 로직 실행 (비동기 스레드에서 실행하여 봇 멈춤 방지)
        new_code = await asyncio.to_thread(generate_and_correct_strategy)
        
        if new_code:
            # 백테스트 및 차트 생성 실행
            res_pct, count = await asyncio.to_thread(run_backtest_and_chart)
            
            # 통계 정보 저장 (리포트 전송 시 읽어오기 위함)
            stats_file = f"{REPORT_DIR}/report_stats.txt"
            with open(stats_file, "w") as f:
                f.write(f"{res_pct:.2f},{count}")
            
            await status_msg.edit_text(f"🎉 전략 진화 및 백테스트 성공!\n📈 수익률: {res_pct:.2f}% | 거래: {count}회")
            
            # 자동으로 리포트 결재창 호출
            await send_report_command(update, context)
        else:
            await status_msg.edit_text("❌ AI가 유효한 전략을 생성하지 못했습니다. 로그를 확인해 주세요.")
            
    except Exception as e:
        logger.error(f"진화 중 에러: {e}")
        await status_msg.edit_text(f"⚠️ 진화 중 에러 발생: {str(e)}")

async def send_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/report 명령어: 리포트 차트와 결재 버튼 전송"""
    if str(update.effective_chat.id) != str(CHAT_ID): return 

    report_image = f"{REPORT_DIR}/report.png"
    report_stats = f"{REPORT_DIR}/report_stats.txt"
    candidate_file = f"{STRAT_DIR}/strategy_candidate.py"

    if not os.path.exists(report_image) or not os.path.exists(candidate_file):
        await update.message.reply_text("📦 대기 중인 후보 전략이 없습니다. 먼저 /evolve를 실행하세요.")
        return

    # 통계 읽기
    try:
        with open(report_stats, "r") as f:
            stats = f.read().split(',')
            return_pct, trade_count = stats[0], stats[1]
    except:
        return_pct, trade_count = "N/A", "N/A"

    # 결재 버튼 구성
    keyboard = [
        [InlineKeyboardButton("🚀 실전 Live 투입 (전략 교체)", callback_data="DEPLOY_LIVE")],
        [InlineKeyboardButton("👻 섀도우 모드 투입 (검증용)", callback_data="DEPLOY_SHADOW")],
        [InlineKeyboardButton("⏪ 이전 코드로 롤백", callback_data="ROLLBACK")],
        [InlineKeyboardButton("❌ 후보 반려 및 삭제", callback_data="REJECT")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    with open(report_image, "rb") as photo:
        await context.bot.send_photo(
            chat_id=CHAT_ID,
            photo=photo,
            caption=(
                f"🤖 **[AI 전략 개선 제안서]**\n\n"
                f"📊 최근 10일 수익률: **{return_pct}%**\n"
                f"🔄 총 거래 횟수: {trade_count}회\n\n"
                f"보스, 이 전략을 실전에 반영할까요?"
            ),
            reply_markup=reply_markup
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """버튼 클릭 처리 로직"""
    query = update.callback_query
    if str(update.effective_chat.id) != str(CHAT_ID):
        await query.answer("접근 권한이 없습니다.")
        return

    await query.answer() 
    
    live_strat = f"{STRAT_DIR}/strategy.py"
    backup_strat = f"{STRAT_DIR}/strategy_backup.py"
    candidate_strat = f"{STRAT_DIR}/strategy_candidate.py"
    shadow_strat = f"{STRAT_DIR}/strategy_shadow.py"
    
    try:
        if query.data == "DEPLOY_LIVE":
            if os.path.exists(candidate_strat):
                shutil.copyfile(live_strat, backup_strat) # 현재 버전을 백업
                shutil.copyfile(candidate_strat, live_strat) # 후보를 실전으로
                await query.edit_message_caption("✅ **[결재 승인]** 실전 전략이 즉시 교체되었습니다! 메인 봇이 다음 루프부터 새 코드를 사용합니다.")
            else:
                await query.edit_message_caption("⚠️ 오류: 후보 파일이 사라졌습니다.")
            
        elif query.data == "DEPLOY_SHADOW":
            if os.path.exists(candidate_strat):
                shutil.copyfile(candidate_strat, shadow_strat)
                await query.edit_message_caption("👻 **[섀도우 가동]** 후보 전략이 섀도우 모드로 투입되었습니다. 실전과 병렬로 수익률을 추적합니다.")
            
        elif query.data == "ROLLBACK":
            if os.path.exists(backup_strat):
                shutil.copyfile(backup_strat, live_strat)
                await query.edit_message_caption("⏪ **[롤백 완료]** 이전 백업 전략으로 복구되었습니다.")
            else:
                await query.edit_message_caption("⚠️ 백업 파일이 존재하지 않습니다.")
                
        elif query.data == "REJECT":
            if os.path.exists(candidate_strat):
                os.remove(candidate_strat)
            await query.edit_message_caption("❌ **[반려]** 후보 전략이 삭제되었습니다.")
            
    except Exception as e:
        await query.edit_message_caption(f"⚠️ 처리 중 오류 발생: {str(e)}")

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