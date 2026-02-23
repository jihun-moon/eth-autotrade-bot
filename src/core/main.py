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
from utils.ai_analyzer import analyze_market_with_ai
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

# 🌟 펭구(ETH) 운용 설정 (시드 고정 및 스윙 주기)
MAX_PENGU_SEED = 1000.0  # 최대 시드 1000 USDT 고정
TIMEFRAME = '15m'       # 스윙 매매를 위한 15분봉 설정
INTERVAL_MINS = 15      # 루프 실행 간격 (15분)

async def send_telegram_msg(message):
    """텔레그램 메시지 전송 (마크다운 지원)"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
    except Exception as e: 
        logger.error(f"❌ 알림 실패: {e}")

async def run_bot():
    """실전 매매 엔진 (15분 스윙 및 7% 트레일링 스탑 적용)"""
    init_db(); db = SessionLocal()
    last_analysis_hour = -1
    
    # 기존 포지션 복구
    position = db.query(ActivePosition).first()
    if position:
        logger.info(f"♻️ 포지션 복구 완료: {position.pos_type} @ {position.entry_price}")

    await send_telegram_msg(f"🚀 **Bottom-Scanner 스윙 엔진 가동!**\n(주기: {TIMEFRAME} | 시드: {MAX_PENGU_SEED}USDT 고정)")

    while True:
        try:
            # 1. 데이터 및 지표 수집 (15분봉 기준)
            raw_data = fetch_historical_data(timeframe=TIMEFRAME, limit=2000)
            df_ind = add_indicators(raw_data)
            current_time = datetime.now(KST)

            # 2. 정기 AI 분석 보고 (1시간 주기)
            if current_time.hour != last_analysis_hour:
                analysis = await analyze_market_with_ai(df_ind)
                await send_telegram_msg(f"🧠 **AI 정기 시장 분석 ({TIMEFRAME})**\n\n{analysis}")
                last_analysis_hour = current_time.hour

            # 3. 전략 적용
            importlib.reload(strategy)
            df, params = strategy.apply_strategy(df_ind.copy())
            last = df.iloc[-1]
            current_price = last['close']
            poc_level = last['POC']

            # 4. 실전 포지션 관리
            if position is None:
                # 진입 시그널 감시
                if last.get('Long_Signal') or last.get('Short_Signal'):
                    pos_type = "LONG" if last['Long_Signal'] else "SHORT"
                    
                    # 🌟 대응 공식: 시드 2500 USDT 고정 사용
                    balance = fetch_real_balance()
                    use_seed = min(balance, MAX_PENGU_SEED)
                    amount = (use_seed * LEVERAGE) / current_price
                    
                    if await execute_order(pos_type, amount):
                        # DB 저장
                        new_pos = ActivePosition(
                            pos_type=pos_type, entry_time=datetime.now(KST), 
                            entry_price=current_price, amount=amount, 
                            margin=use_seed, tp_pct=params['tp'], sl_pct=params['sl']
                        )
                        db.add(new_pos); db.commit(); position = new_pos
                        await send_telegram_msg(f"🎯 **[{pos_type} 진입]**\n가격: `{current_price:,.2f}`\n시드: `{use_seed:,.2f} USDT`")
            else:
                # 🛡️ [업그레이드: 본절가 트레일링 스탑]
                # 가격이 POC에 도달하면 손절가를 본절(0)로 이동
                if position.pos_type == "LONG" and current_price >= poc_level > position.entry_price:
                    if position.sl_pct != 0:
                        position.sl_pct = 0; db.commit()
                        await send_telegram_msg("🛡️ **가격이 POC에 도달하여 손절가를 본절로 옮겼습니다.**")
                
                elif position.pos_type == "SHORT" and current_price <= poc_level < position.entry_price:
                    if position.sl_pct != 0:
                        position.sl_pct = 0; db.commit()
                        await send_telegram_msg("🛡️ **가격이 POC에 도달하여 손절가를 본절로 옮겼습니다.**")

                # 수익률(ROE) 계산
                roe = ((current_price - position.entry_price) / position.entry_price * LEVERAGE 
                       if position.pos_type == "LONG" else (position.entry_price - current_price) / position.entry_price * LEVERAGE)
                
                # 🛡️ [고도화 대응 공식: 7% 익절 보존]
                # ROE가 7%를 넘어서면 손절가를 +5% 지점으로 상향 (익절 보존)
                if roe >= 0.07 and position.sl_pct > -0.005: # -0.005는 진입가보다 유리한 5% 수익 구간 스탑 의미
                    position.sl_pct = -0.005 # 내부 로직상 진입가보다 앞선 구간
                    db.commit()
                    await send_telegram_msg("🔥 **ROE 7% 돌파!**\n수익 보존을 위해 익절 라인을 +5% 구간으로 상향 조정했습니다.")

                # 청산 조건 확인
                exit_condition = False
                reason = ""

                if roe >= (position.tp_pct * LEVERAGE):
                    exit_condition = True; reason = "익절(TP)"
                elif position.sl_pct == 0 and roe <= -0.001:  # 본절 보호 상태에서 진입가 이탈 시
                    exit_condition = True; reason = "본절보호(Break-even)"
                elif position.sl_pct == -0.005 and roe <= 0.05: # 7% 돌파 후 5% 익절 라인 터치 시
                    exit_condition = True; reason = "익절보존(Trailing)"
                elif position.sl_pct > 0 and roe <= -(position.sl_pct * LEVERAGE):
                    exit_condition = True; reason = "손절(SL)"

                if exit_condition:
                    if await execute_order('EXIT', position.amount):
                        db.query(ActivePosition).delete(); db.commit()
                        await send_telegram_msg(f"🏁 **포지션 종료**\n사유: `{reason}`\n최종 ROE: `{roe*100:+.2f}%`")
                        position = None

            # 5. 정밀 대기 (15분 주기에 맞춤)
            now = datetime.now(KST)
            next_run = now.replace(second=5, microsecond=0) + timedelta(minutes=INTERVAL_MINS - (now.minute % INTERVAL_MINS))
            wait_sec = (next_run - now).total_seconds()
            if wait_sec < 0: wait_sec += (INTERVAL_MINS * 60)
            await asyncio.sleep(max(wait_sec, 10))
            
        except Exception as e:
            # 🚑 AI 에러 자가 진단
            error_trace = traceback.format_exc()
            diag_msg = await analyze_market_with_ai(error_msg=str(e))
            
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