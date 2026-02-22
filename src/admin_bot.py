import os
import shutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 🌟 추가됨: 봇을 처음 켰을 때(또는 /start 입력 시) 명령어 안내
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start 명령어 입력 시 인사말과 명령어 안내"""
    user_chat_id = str(update.effective_chat.id)
    if user_chat_id != str(CHAT_ID):
        print(f"⚠️ [경고] 권한 없는 사용자의 접근 시도 차단! (ID: {user_chat_id})")
        return

    welcome_msg = (
        "안녕하세요 보스! 퀀트 트레이딩 비서 봇입니다. 🤖\n\n"
        "아래 명령어를 클릭하거나 입력해 주세요:\n"
        "👉 /report : 최신 AI 전략 개선 제안서 확인 및 결재\n"
        "👉 /start : 이 안내 메시지 다시 보기"
    )
    await update.message.reply_text(welcome_msg)

async def send_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/report 명령어 입력 시 진화 리포트와 버튼 전송"""
    user_chat_id = str(update.effective_chat.id)
    if user_chat_id != str(CHAT_ID):
        print(f"⚠️ [경고] 권한 없는 사용자의 접근 시도 차단! (ID: {user_chat_id})")
        return 

    if not os.path.exists("report.png") or not os.path.exists("src/strategy_candidate.py"):
        await update.message.reply_text("아직 대기 중인 AI 후보 전략이 없습니다. 서버에서 'python src/evolve.py'를 실행하세요.")
        return

    with open("report_stats.txt", "r") as f:
        stats = f.read().split(',')
        return_pct = stats[0]

    keyboard = [
        [InlineKeyboardButton("🚀 실전 Live 투입 (기존 덮어쓰기)", callback_data="DEPLOY_LIVE")],
        [InlineKeyboardButton("👻 섀도우 모드 투입 (안전 검증)", callback_data="DEPLOY_SHADOW")],
        [InlineKeyboardButton("⏪ 이전 코드로 롤백 (긴급 복구)", callback_data="ROLLBACK")],
        [InlineKeyboardButton("❌ 반려 (삭제)", callback_data="REJECT")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    with open("report.png", "rb") as photo:
        await context.bot.send_photo(
            chat_id=CHAT_ID,
            photo=photo,
            caption=f"🤖 **[AI 전략 개선 제안서]**\n\n📈 백테스트 예상 수익률: {return_pct}%\n어떻게 처리할까요?",
            reply_markup=reply_markup
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    user_chat_id = str(update.effective_chat.id)
    if user_chat_id != str(CHAT_ID):
        await query.answer("❌ 권한이 없습니다. 관리자만 조작 가능합니다.", show_alert=True)
        return

    await query.answer() 
    
    if query.data == "DEPLOY_LIVE":
        shutil.copyfile("src/strategy.py", "src/strategy_backup.py")
        shutil.copyfile("src/strategy_candidate.py", "src/strategy.py")
        await query.edit_message_caption("✅ 실전 투입 완료! 메인 봇이 다음 캔들부터 새 코드로 매매합니다.")
        
    elif query.data == "DEPLOY_SHADOW":
        shutil.copyfile("src/strategy_candidate.py", "src/strategy_shadow.py")
        await query.edit_message_caption("👻 섀도우 모드 투입 완료! 메인 봇이 백그라운드에서 성과를 추적합니다.")
        
    elif query.data == "ROLLBACK":
        if os.path.exists("src/strategy_backup.py"):
            shutil.copyfile("src/strategy_backup.py", "src/strategy.py")
            await query.edit_message_caption("⏪ 롤백 완료! 이전 버전 코드로 즉시 복구되었습니다.")
        else:
            await query.edit_message_caption("⚠️ 백업 파일이 존재하지 않아 롤백할 수 없습니다!")
            
    elif query.data == "REJECT":
        if os.path.exists("src/strategy_candidate.py"):
            os.remove("src/strategy_candidate.py")
        await query.edit_message_caption("❌ 반려되었습니다. 후보 코드를 폐기합니다.")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # 🌟 명령어 핸들러 등록
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command)) # /help를 쳐도 안내가 나오게 추가
    app.add_handler(CommandHandler("report", send_report_command))
    
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("👔 텔레그램 결재 대기 봇 가동 중...")
    app.run_polling()