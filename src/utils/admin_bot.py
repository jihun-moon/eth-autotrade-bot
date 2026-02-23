import os
import shutil
import asyncio
import logging
import sys
import ccxt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# 🌟 경로 설정: 상위 폴더(src)를 인식하여 패키지들을 찾을 수 있게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 필수 모듈 임포트
from core.db_manager import SessionLocal, ActivePosition
from core.trader import get_exchange
from research.evolve import generate_and_correct_strategy, run_backtest_and_chart
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
from utils.ai_analyzer import analyze_market_with_ai

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 전역 변수 설정
STRAT_DIR = "src/strategies"
REPORT_DIR = "data/reports"
LEVERAGE = 10 
TIMEFRAME = '15m'  # 🌟 스윙 매매 타임프레임 고정

logger = logging.getLogger("AdminBot")

async def generate_market_chart(df):
    """🌟 15분봉 기준 실시간 스윙 분석 차트 이미지(PNG) 생성"""
    # 스윙 매매이므로 흐름 파악을 위해 최근 120개의 캔들 시각화
    window = df.tail(120)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # 1. 캔들스틱 차트 추가
    fig.add_trace(go.Candlestick(
        x=window.index, open=window['open'], high=window['high'], 
        low=window['low'], close=window['close'], name='Price'
    ), row=1, col=1)

    # 2. 매물대 라인 추가 (트레이딩뷰 정밀 이식 버전 반영)
    last_val = window['VAL'].iloc[-1]
    last_poc = window['POC'].iloc[-1]
    last_vah = window['VAH'].iloc[-1]

    for level, color, name in [(last_val, 'blue', 'VAL'), (last_poc, 'orange', 'POC'), (last_vah, 'red', 'VAH')]:
        fig.add_hline(y=level, line_dash="dash", line_color=color, 
                      annotation_text=f"{name} ({level:.2f})", row=1, col=1)

    # 3. CVD 지표 추가
    fig.add_trace(go.Scatter(x=window.index, y=window['CVD'], name='CVD', line=dict(color='green')), row=2, col=1)
    fig.add_trace(go.Scatter(x=window.index, y=window['CVD_Signal'], name='Signal', line=dict(color='gray', dash='dot')), row=2, col=1)

    # 레이아웃 설정 (15m 스윙 테마)
    fig.update_layout(
        title=f"🚀 ETH/USDT {TIMEFRAME} Swing Analysis ({datetime.now().strftime('%H:%M:%S')})",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        width=1000, height=800,
        showlegend=False
    )
    
    img_path = os.path.join(REPORT_DIR, "live_chart.png")
    fig.write_image(img_path)
    return img_path

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start: 메뉴 안내 및 인사"""
    if str(update.effective_chat.id) != str(CHAT_ID): return
    msg = (
        "👋 **안녕하세요 보스! Bottom-Scanner 스윙 에이전트입니다.**\n\n"
        f"현재 시스템은 **{TIMEFRAME}봉** 기반으로 큰 추세를 추적 중입니다. 📈\n\n"
        "💬 **대화형 분석**: 궁금한 내용을 입력하세요!\n"
        "   (예: '지금 진입해도 괜찮을까?', '매물대 상황 알려줘')\n\n"
        "⚙️ **관리 명령어**\n"
        "🔹 /status : 실시간 포지션 및 수익률 확인\n"
        "🔹 /evolve : AI 전략 자가 학습 (15m 최적화)\n"
        "🔹 /report : 최근 생성된 리포트 차트 보기"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🌟 분석 답변을 사진과 텍스트로 분리하여 전송"""
    if str(update.effective_chat.id) != str(CHAT_ID): return
    
    user_text = update.message.text
    thinking_msg = await update.message.reply_text(f"🤔 **보스의 질문을 {TIMEFRAME} 기준으로 분석 중입니다...**")
    
    try:
        # 1. 15분봉 데이터 수집 및 지표 계산
        raw_df = fetch_historical_data(timeframe=TIMEFRAME, limit=1000)
        df = add_indicators(raw_df)
        
        # 2. 실시간 분석 차트 이미지 생성
        img_path = await generate_market_chart(df)
        
        # 3. AI 분석 답변 생성
        analysis = await analyze_market_with_ai(df, user_text)
        
        # 4. 사진 전송
        with open(img_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=CHAT_ID, 
                photo=photo, 
                caption=f"📊 **ETH/USDT {TIMEFRAME} 실시간 스윙 리포트**"
            )
        
        # 5. 상세 분석 텍스트 전송
        await update.message.reply_text(f"🧠 **AI 정밀 분석 결과**\n\n{analysis}", parse_mode='Markdown')
        await thinking_msg.delete()
        
    except Exception as e:
        logger.error(f"채팅 처리 중 에러: {e}")
        await thinking_msg.edit_text(f"❌ **에러 발생**: {str(e)}")

async def status_command(update, context):
    """/status: 현재 포지션 및 ROE 조회 (스윙 기준)"""
    if str(update.effective_chat.id) != str(CHAT_ID): return
    db = SessionLocal()
    try:
        pos = db.query(ActivePosition).first()
        if not pos:
            await update.message.reply_text("📭 **현재 보유 중인 포지션이 없습니다.**")
            return

        exchange = get_exchange() or ccxt.binance({'enableRateLimit': True})
        ticker = await asyncio.to_thread(exchange.fetch_ticker, 'ETH/USDT')
        current_price = ticker['last']

        roe = ((current_price - pos.entry_price) / pos.entry_price * LEVERAGE 
               if pos.pos_type == "LONG" else (pos.entry_price - current_price) / pos.entry_price * LEVERAGE)
        
        status_msg = (
            f"📊 **스윙 포지션 브리핑**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔹 **타입**: `{pos.pos_type}` ({LEVERAGE}x)\n"
            f"🔹 **진입가**: `{pos.entry_price:,.2f} USDT`\n"
            f"🔹 **현재가**: `{current_price:,.2f} USDT`\n\n"
            f"🔥 **실시간 ROE: {roe*100:+.2f}%**\n"
            f"⏰ **진입시간**: {pos.entry_time.strftime('%m/%d %H:%M:%S')}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(status_msg, parse_mode='Markdown')
    finally: db.close()

async def evolve_command(update, context):
    """/evolve: AI 전략 진화 프로세스 (15m 스윙 최적화)"""
    if str(update.effective_chat.id) != str(CHAT_ID): return
    msg = await update.message.reply_text(f"🤖 **AI가 {TIMEFRAME} 데이터를 학습하며 전략을 진화시키고 있습니다...**")
    try:
        success, reason = await asyncio.to_thread(generate_and_correct_strategy)
        
        if success:
            pct, count = await asyncio.to_thread(run_backtest_and_chart)
            await msg.edit_text(
                f"🎉 **스윙 최적화 전략이 탄생했습니다!**\n\n"
                f"📈 **기대 수익률**: `{pct:.2f}%` (수수료 0.04% 차감 후)\n"
                f"📊 **테스트 거래**: `{count}회` (최근 15분봉 데이터 기준)\n\n"
                f"상세 리포트 차트를 전송합니다..."
            )
            await send_report_command(update, context)
        else:
            error_report = (
                f"❌ **전략 진화 실패**\n\n"
                f"🧐 **원인**: {reason[:500]}..." 
            )
            await msg.edit_text(error_report)
            
    except Exception as e: 
        await msg.edit_text(f"⚠️ **시스템 에러**: {str(e)}")

async def send_report_command(update, context):
    """/report: 후보 전략 리포트 확인"""
    if str(update.effective_chat.id) != str(CHAT_ID): return
    report_path = os.path.join(REPORT_DIR, "report.png")
    
    if not os.path.exists(report_path):
        await update.message.reply_text("📦 **대기 중인 리포트가 없습니다. /evolve를 실행하세요.**")
        return

    keyboard = [[InlineKeyboardButton("🚀 실전 Live 투입", callback_data="DEPLOY_LIVE")]]
    
    with open(report_path, "rb") as photo:
        await context.bot.send_photo(
            chat_id=CHAT_ID, 
            photo=photo, 
            caption=f"🤖 **AI 개선 스윙 전략 승인 요청**\n보스, 이 {TIMEFRAME} 전략을 실전에 반영할까요?", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def button_callback(update, context):
    """결재 버튼 클릭 처리"""
    query = update.callback_query
    await query.answer()
    if query.data == "DEPLOY_LIVE":
        live_strat = os.path.join(STRAT_DIR, "strategy.py")
        candidate_strat = os.path.join(STRAT_DIR, "strategy_candidate.py")
        shutil.copyfile(candidate_strat, live_strat)
        await query.edit_message_caption("✅ **결재 승인!** 15분봉 스윙 전략이 즉시 교체되었습니다.")

if __name__ == "__main__":
    os.makedirs(STRAT_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("report", send_report_command))
    app.add_handler(CommandHandler("evolve", evolve_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print(f"👔 Bottom-Scanner 스윙 엔진 가동 중 ({TIMEFRAME} 모드)...")
    app.run_polling()