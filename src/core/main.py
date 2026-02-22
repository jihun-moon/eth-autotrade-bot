import os
import asyncio
import logging
import importlib
import traceback
from datetime import datetime, timedelta, timezone
from telegram import Bot
from dotenv import load_dotenv

# 필수 유틸리티 및 전략 임포트
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators
from utils.ai_analyzer import analyze_market_with_ai  # 업그레이드된 분석기
import strategies.strategy as strategy 
from core.db_manager import init_db, SessionLocal, ActivePosition
from core.trader import fetch_real_balance, execute_order 

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
                    handlers=[logging.FileHandler("data/reports/bot.log"), logging.StreamHandler()])
logger = logging.getLogger("BottomScanner")

load_dotenv()
TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_TOKEN'), os.getenv('TELEGRAM_CHAT_ID')
KST, LEVERAGE = timezone(timedelta(hours=9)), 10

async def send_telegram_msg(message):
    """텔레그램 메시지 전송 (마크다운 지원)"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
    except Exception as e: 
        logger.error(f"❌ 알림 실패: {e}")

async def run_bot():
    """실전 매매 엔진 (트레일링 스탑 및 자가 진단 포함)"""
    init_db(); db = SessionLocal()
    last_analysis_hour = -1
    
    # 기존 포지션 복구
    position = db.query(ActivePosition).first()
    if position:
        logger.info(f"♻️ 포지션 복구 완료: {position.pos_type} @ {position.entry_price}")

    await send_telegram_msg("🚀 **Bottom-Scanner 엔진 가동!**\n(본절가 보호 트레일링 스탑 활성화)")

    while True:
        try:
            # 1. 데이터 및 지표 수집
            raw_data = fetch_historical_data(limit=2000)
            df_ind = add_indicators(raw_data)
            current_time = datetime.now(KST)

            # 2. 정기 AI 분석 보고 (1시간 주기)
            if current_time.hour != last_analysis_hour:
                analysis = await analyze_market_with_ai(df_ind)
                await send_telegram_msg(f"🧠 **AI 정기 시장 분석**\n\n{analysis}")
                last_analysis_hour = current_time.hour

            # 3. 전략 적용
            importlib.reload(strategy)
            df, params = strategy.apply_strategy(df_ind.copy())
            last = df.iloc[-1]
            current_price = last['close']
            poc_level = last['POC']  # 🌟 지표에서 POC 값 추출

            # 4. 실전 포지션 관리
            if position is None:
                # 진입 시그널 감시
                if last.get('Long_Signal') or last.get('Short_Signal'):
                    pos_type = "LONG" if last['Long_Signal'] else "SHORT"
                    balance = fetch_real_balance()
                    amount = (balance * LEVERAGE) / current_price
                    
                    if await execute_order(pos_type, amount):
                        # DB 저장
                        new_pos = ActivePosition(
                            pos_type=pos_type, entry_time=datetime.now(KST), 
                            entry_price=current_price, amount=amount, 
                            margin=balance, tp_pct=params['tp'], sl_pct=params['sl']
                        )
                        db.add(new_pos); db.commit(); position = new_pos
                        await send_telegram_msg(f"🎯 **[{pos_type} 진입]** 가격: `{current_price:,.2f}`")
            else:
                # 🛡️ [업그레이드: 본절가 트레일링 스탑] POC 도달 시 SL을 진입가로 이동
                if position.pos_type == "LONG" and current_price >= poc_level > position.entry_price:
                    if position.sl_pct != 0:  # 0은 본절 보호 모드 활성화를 의미함
                        position.sl_pct = 0; db.commit()
                        await send_telegram_msg("🛡️ **가격이 POC에 도달하여 손절가를 본절로 옮겼습니다. (무위험 거래 전환)**")
                
                elif position.pos_type == "SHORT" and current_price <= poc_level < position.entry_price:
                    if position.sl_pct != 0:
                        position.sl_pct = 0; db.commit()
                        await send_telegram_msg("🛡️ **가격이 POC에 도달하여 손절가를 본절로 옮겼습니다. (무위험 거래 전환)**")

                # 수익률(ROE) 계산
                roe = ((current_price - position.entry_price) / position.entry_price * LEVERAGE 
                       if position.pos_type == "LONG" else (position.entry_price - current_price) / position.entry_price * LEVERAGE)
                
                # 청산 조건 확인 (익절, 손절, 또는 본절 보호 스탑)
                exit_condition = False
                reason = ""

                if roe >= (position.tp_pct * LEVERAGE):
                    exit_condition = True; reason = "익절(TP)"
                elif position.sl_pct == 0 and roe <= -0.001:  # 본절 보호 상태에서 진입가 이탈 시
                    exit_condition = True; reason = "본절보호(Break-even)"
                elif position.sl_pct != 0 and roe <= -(position.sl_pct * LEVERAGE):
                    exit_condition = True; reason = "손절(SL)"

                if exit_condition:
                    if await execute_order('EXIT', position.amount):
                        db.query(ActivePosition).delete(); db.commit()
                        await send_telegram_msg(f"🏁 **포지션 종료**\n사유: `{reason}`\n최종 ROE: `{roe*100:+.2f}%`")
                        position = None

            # 5. 정밀 대기 (3분 05초 타이밍)
            now = datetime.now(KST)
            next_run = now.replace(second=5, microsecond=0) + timedelta(minutes=3 - (now.minute % 3))
            wait_sec = (next_run - now).total_seconds()
            if wait_sec < 0: wait_sec += 180 
            await asyncio.sleep(max(wait_sec, 10))
            
        except Exception as e:
            # 🚑 [업그레이드: AI 에러 자가 진단]
            error_trace = traceback.format_exc()
            diag_msg = await analyze_market_with_ai(error_msg=str(e)) # AI에게 에러 분석 요청
            
            await send_telegram_msg(
                f"🚨 **시스템 에러 및 AI 자가 진단**\n"
                f"━━━━━━━━━━━━━━\n"
                f"❌ **내용**: `{str(e)}`\n"
                f"🧠 **AI 처방**: {diag_msg}\n"
                f"━━━━━━━━━━━━━━"
            )
            logger.error(f"메인 루프 에러: {error_trace}")
            db.rollback(); await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(run_bot())