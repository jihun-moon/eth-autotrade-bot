import os
import asyncio
import pandas as pd
import importlib
from datetime import datetime, timedelta, timezone
from telegram import Bot
from dotenv import load_dotenv

# [경로 수정] 새 구조에 맞춘 유틸리티 모듈 임포트
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

# [경로 수정] 전략 모듈 임포트 (패키지 경로 적용)
import strategies.strategy as strategy 

load_dotenv()

# 환경 변수 및 설정
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BOT_NAME = "Bottom-Scanner" 
KST = timezone(timedelta(hours=9))

# 매매 파라미터
INITIAL_BALANCE = 1300.0  
LEVERAGE = 10             
TP_PCT = 0.02             
SL_PCT = 0.015             
FEE_RATE = 0.0005         

# [경로 수정] 지훈님 의견 반영: 모든 리포트는 data/reports 폴더에 저장
REPORT_DIR = "data/reports"
HISTORY_FILE = f"{REPORT_DIR}/trade_history.csv"

# 필요한 폴더 생성
if not os.path.exists(REPORT_DIR):
    os.makedirs(REPORT_DIR)

async def send_telegram_msg(message):
    """텔레그램 알림 전송"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"[{BOT_NAME}]\n{message}")
    except Exception as e:
        print(f"❌ 텔레그램 알림 전송 실패: {e}")

def save_trade_history(trade_data):
    """매매 기록을 CSV에 저장"""
    df = pd.DataFrame([trade_data])
    if not os.path.exists(HISTORY_FILE):
        df.to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')
    else:
        df.to_csv(HISTORY_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')

async def run_bot():
    print(f"🚀 [{BOT_NAME}] 실전 & 섀도우 봇 동시 가동! (구조 개편 버전)")
    
    balance = INITIAL_BALANCE
    position = None 
    shadow_position = None 
    
    TARGET_ROE = TP_PCT * LEVERAGE      
    STOPLOSS_ROE = -(SL_PCT * LEVERAGE) 
    
    await send_telegram_msg(f"✅ 양방향 풀-오토 가동 시작! (레버리지 {LEVERAGE}x)\n📊 로그 위치: {HISTORY_FILE}")

    while True:
        try:
            # 1. 최신 데이터 수집 및 지표 계산
            df_raw = fetch_historical_data(limit=1000)
            df_ind = add_indicators(df_raw)
            
            # --- 1. 실전(Live) 전략 실행 ---
            importlib.reload(strategy) 
            df = strategy.apply_strategy(df_ind.copy(), ema_len=30)
            last = df.iloc[-1]
            
            # --- 2. 섀도우(Shadow) 검증 봇 실행 및 알림 ---
            shadow_strat_path = "src/strategies/strategy_shadow.py"
            if os.path.exists(shadow_strat_path):
                try:
                    import strategies.strategy_shadow as strategy_shadow
                    importlib.reload(strategy_shadow)
                    df_shadow = strategy_shadow.apply_strategy(df_ind.copy(), ema_len=30)
                    last_shadow = df_shadow.iloc[-1]
                    
                    # 섀도우 진입 시 알림
                    if shadow_position is None and (last_shadow.get('Long_Signal') or last_shadow.get('Short_Signal')):
                        pos_type = "LONG" if last_shadow['Long_Signal'] else "SHORT"
                        shadow_position = {'type': pos_type, 'price': last_shadow['close']}
                        msg = f"👻 [섀도우 진입] {pos_type} 가상 포지션 시작\n💰 가격: {last_shadow['close']:.2f} USDT"
                        print(msg)
                        await send_telegram_msg(msg)
                    
                    # 섀도우 결과 알림
                    elif shadow_position is not None:
                        if shadow_position['type'] == 'LONG':
                            shadow_roe = (last_shadow['close'] - shadow_position['price']) / shadow_position['price'] * LEVERAGE
                        else: # SHORT
                            shadow_roe = (shadow_position['price'] - last_shadow['close']) / shadow_position['price'] * LEVERAGE
                        
                        if shadow_roe >= TARGET_ROE:
                            msg = f"👻 [섀도우 익절] 🎯 타겟 도달!\n📈 ROE: +{shadow_roe*100:.2f}%"
                            print(msg)
                            await send_telegram_msg(msg)
                            shadow_position = None
                        elif shadow_roe <= STOPLOSS_ROE:
                            msg = f"👻 [섀도우 손절] ❌ 리스크 관리 종료\n📉 ROE: {shadow_roe*100:.2f}%"
                            print(msg)
                            await send_telegram_msg(msg)
                            shadow_position = None
                except Exception as e:
                    print(f"⚠️ 섀도우 봇 에러: {e}")

            current_time = datetime.now(KST)
            current_price = last['close']
            
            # --- 3. 실전 포지션 진입/청산 로직 ---
            if position is None:
                if last['Long_Signal'] or last['Short_Signal']:
                    pos_type = "LONG" if last['Long_Signal'] else "SHORT"
                    entry_price = current_price
                    position_size = balance * LEVERAGE 
                    entry_fee = position_size * FEE_RATE
                    balance -= entry_fee 
                    
                    position = {
                        'type': pos_type,
                        'entry_time': current_time, 
                        'entry_price': entry_price, 
                        'initial_investment': balance + entry_fee, 
                        'margin': balance,
                        'amount': position_size / entry_price,
                        'size': position_size,
                        'entry_fee': entry_fee
                    }
                    msg = (f"🎯 [{pos_type} 진입!]\n💰 진입가: {entry_price:.2f} USDT\n🔥 총 포지션: {position_size:.2f} USDT")
                    print(msg)
                    await send_telegram_msg(msg)
                else:
                    print(f"🔍 [감시 중] {current_time.strftime('%H:%M:%S')} | 가격: {current_price:.2f} | 대기...")
            
            else:
                pos_type = position['type']
                current_size = position['amount'] * current_price
                exit_fee = current_size * FEE_RATE
                
                if pos_type == "LONG":
                    gross_pnl = current_size - position['size']
                else:
                    gross_pnl = position['size'] - current_size 
                
                net_trade_pnl = gross_pnl - position['entry_fee'] - exit_fee
                roe_pct = net_trade_pnl / position['initial_investment']
                
                close_reason = None
                if roe_pct <= -1.0:
                    balance = 0
                    close_reason = "강제청산(LIQ)"
                elif roe_pct >= TARGET_ROE:
                    balance = position['margin'] + gross_pnl - exit_fee
                    close_reason = "익절(TP)"
                elif roe_pct <= STOPLOSS_ROE:
                    balance = position['margin'] + gross_pnl - exit_fee
                    close_reason = "손절(SL)"

                if close_reason:
                    msg = f"🏁 [{close_reason} 완료] {pos_type} 종료\n💵 순손익: {net_trade_pnl:.2f} USDT (ROE: {roe_pct*100:.2f}%)"
                    print(msg)
                    await send_telegram_msg(msg)
                    
                    # 매매 일지 기록
                    save_trade_history({
                        "진입시간": position['entry_time'].strftime('%Y-%m-%d %H:%M:%S'),
                        "청산시간": current_time.strftime('%Y-%m-%d %H:%M:%S'),
                        "포지션": pos_type,
                        "진입가": round(position['entry_price'], 2),
                        "청산가": round(current_price, 2),
                        "순손익(USDT)": round(net_trade_pnl, 2),
                        "최종ROE(%)": round(roe_pct * 100, 2),
                        "종료사유": close_reason
                    })
                    position = None
                    if close_reason == "강제청산(LIQ)": break

            # 3분 주기 슬립
            now = datetime.now(KST)
            next_run = now.replace(second=0, microsecond=0) + timedelta(minutes=3 - (now.minute % 3))
            sleep_seconds = (next_run - now).total_seconds()
            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)
            
        except Exception as e:
            print(f"⚠️ 봇 실행 중 에러 발생: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_bot())