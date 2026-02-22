import os
import asyncio
import pandas as pd
import importlib
from datetime import datetime, timedelta, timezone
from telegram import Bot
from dotenv import load_dotenv
from fetcher import fetch_historical_data
from indicators import add_indicators

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BOT_NAME = "Bottom-Scanner" 
KST = timezone(timedelta(hours=9))

INITIAL_BALANCE = 1300.0  
LEVERAGE = 10             
TP_PCT = 0.02             
SL_PCT = 0.015             
FEE_RATE = 0.0005         

DB_DIR = "db"
HISTORY_FILE = f"{DB_DIR}/trade_history.csv"

if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

async def send_telegram_msg(message):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"[{BOT_NAME}]\n{message}")
    except Exception as e:
        print(f"❌ 텔레그램 알림 전송 실패: {e}")

def save_trade_history(trade_data):
    df = pd.DataFrame([trade_data])
    if not os.path.exists(HISTORY_FILE):
        df.to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')
    else:
        df.to_csv(HISTORY_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')

async def run_bot():
    print(f"🚀 [{BOT_NAME}] 실전 & 섀도우 봇 동시 가동!")
    
    balance = INITIAL_BALANCE
    position = None 
    shadow_position = None # 🌟 섀도우 포지션
    
    TARGET_ROE = TP_PCT * LEVERAGE      
    STOPLOSS_ROE = -(SL_PCT * LEVERAGE) 
    
    await send_telegram_msg(f"✅ 양방향 풀-오토 가동 시작! (레버리지 {LEVERAGE}x)")

    while True:
        try:
            df_raw = fetch_historical_data(limit=1000)
            df_ind = add_indicators(df_raw)
            
            # --- 1. 실전(Live) 전략 실행 ---
            # 🌟 매번 모듈을 리로드하여, 결재가 나면 봇 재부팅 없이 다음 캔들부터 바로 새 코드 적용
            import strategy
            importlib.reload(strategy)
            df = strategy.apply_strategy(df_ind.copy(), ema_len=30)
            last = df.iloc[-1]
            
            # --- 2. 섀도우(Shadow) 검증 봇 실행 ---
            if os.path.exists("src/strategy_shadow.py"):
                try:
                    import strategy_shadow
                    importlib.reload(strategy_shadow)
                    df_shadow = strategy_shadow.apply_strategy(df_ind.copy(), ema_len=30)
                    last_shadow = df_shadow.iloc[-1]
                    
                    if shadow_position is None and (last_shadow.get('Long_Signal') or last_shadow.get('Short_Signal')):
                        pos_type = "LONG" if last_shadow['Long_Signal'] else "SHORT"
                        shadow_position = {'type': pos_type, 'price': last_shadow['close']}
                        print(f"👻 [섀도우 검증] {pos_type} 가상 진입 포착! (가격: {last_shadow['close']})")
                    elif shadow_position is not None:
                        roe_diff = abs((last_shadow['close'] - shadow_position['price']) / shadow_position['price'] * LEVERAGE)
                        if roe_diff >= TP_PCT or roe_diff >= SL_PCT:
                            print(f"👻 [섀도우 검증] 가상 포지션 종료 완료.")
                            shadow_position = None
                except Exception as e:
                    pass # 섀도우 에러는 메인 봇에 영향을 주지 않게 무시

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
                    msg = f"🏁 [{close_reason} 완료] {pos_type} 포지션 종료\n💵 순손익: {net_trade_pnl:.2f} USDT (ROE: {roe_pct*100:.2f}%)"
                    print(msg)
                    await send_telegram_msg(msg)
                    position = None
                    if close_reason == "강제청산(LIQ)": break

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