import os
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from telegram import Bot
from dotenv import load_dotenv
from fetcher import fetch_historical_data
from indicators import add_indicators
from strategy import apply_strategy

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BOT_NAME = "Bottom-Scanner" 

# --- 가상 투자(모의투자) 설정 ---
INITIAL_BALANCE = 1300.0  
LEVERAGE = 10             
TP_PCT = 0.02             
SL_PCT = 0.015             
FEE_RATE = 0.0005         # 💸 바이낸스 선물 시장가 수수료 0.05%
# -----------------------------

DB_DIR = "db"
HISTORY_FILE = f"{DB_DIR}/trade_history.csv"

if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

async def send_telegram_msg(message):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        full_msg = f"[{BOT_NAME}]\n{message}"
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=full_msg)
    except Exception as e:
        print(f"❌ 텔레그램 알림 전송 실패: {e}")

def save_trade_history(trade_data):
    df = pd.DataFrame([trade_data])
    if not os.path.exists(HISTORY_FILE):
        df.to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')
    else:
        df.to_csv(HISTORY_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')
    print(f"💾 매매 일지가 엑셀(CSV) 파일에 안전하게 기록되었습니다.")

async def run_bot():
    print(f"🚀 [{BOT_NAME}] 양방향(LONG/SHORT) 모의투자 봇 가동!")
    
    balance = INITIAL_BALANCE
    position = None 
    
    TARGET_ROE = TP_PCT * LEVERAGE      
    STOPLOSS_ROE = -(SL_PCT * LEVERAGE) 
    
    await send_telegram_msg(
        f"✅ 양방향(LONG/SHORT) 풀-오토 가동 시작!\n"
        f"⚙️ 레버리지: {LEVERAGE}x\n"
        f"💰 시작 잔고: {balance:.2f} USDT"
    )

    while True:
        try:
            df = fetch_historical_data(limit=1000)
            df = add_indicators(df)
            df = apply_strategy(df, ema_len=30)
            
            last = df.iloc[-1]
            current_time = datetime.now()
            current_price = last['close']
            
            # ==========================================
            # 2. 포지션 진입 감시 (롱 or 숏)
            # ==========================================
            if position is None:
                # 롱 시그널이 떴는지, 숏 시그널이 떴는지 확인
                if last['Long_Signal'] or last['Short_Signal']:
                    pos_type = "LONG" if last['Long_Signal'] else "SHORT"
                    entry_price = current_price
                    
                    position_size = balance * LEVERAGE 
                    entry_fee = position_size * FEE_RATE
                    balance -= entry_fee 
                    
                    margin = balance
                    amount = position_size / entry_price 
                    
                    position = {
                        'type': pos_type, # 🌟 롱/숏 방향 기억
                        'entry_time': current_time, 
                        'entry_price': entry_price, 
                        'initial_investment': margin + entry_fee, 
                        'margin': margin,
                        'amount': amount,
                        'size': position_size,
                        'entry_fee': entry_fee
                    }
                    
                    # 롱/숏 이모지 다르게 표시
                    icon = "📈" if pos_type == "LONG" else "📉"
                    msg = (f"🎯 [가상 {pos_type} 진입! ({LEVERAGE}x)]\n"
                           f"⏰ 시간: {current_time.strftime('%H:%M:%S')}\n"
                           f"💰 진입가: {entry_price:.2f} USDT\n"
                           f"{icon} 방향: {pos_type}\n"
                           f"🔥 총 포지션: {position_size:.2f} USDT\n"
                           f"💸 낸 수수료: {entry_fee:.2f} USDT")
                    print(msg)
                    await send_telegram_msg(msg)
                else:
                    print(f"🔍 [감시 중] {current_time.strftime('%H:%M:%S')} | 가격: {current_price:.2f} | 진입 대기...")
            
            # ==========================================
            # 3. 포지션 청산 감시 (수수료 및 방향성 반영)
            # ==========================================
            else:
                pos_type = position['type']
                entry_time = position['entry_time']
                entry_price = position['entry_price']
                margin = position['margin']
                initial_investment = position['initial_investment']
                amount = position['amount']
                entry_fee = position['entry_fee']
                
                current_size = amount * current_price
                exit_fee = current_size * FEE_RATE
                
                # 🌟 롱과 숏의 수익 계산법 분리
                if pos_type == "LONG":
                    gross_pnl = current_size - position['size'] # 올랐을 때 수익
                else: # SHORT
                    gross_pnl = position['size'] - current_size # 떨어졌을 때 수익
                
                net_trade_pnl = gross_pnl - entry_fee - exit_fee
                roe_pct = net_trade_pnl / initial_investment
                
                print(f"🔒 [{pos_type} 보유] 현재가: {current_price:.2f} | 찐ROE: {roe_pct*100:.2f}% | 순손익: {net_trade_pnl:.2f}")
                
                close_reason = None

                if roe_pct <= -1.0:
                    balance = 0
                    close_reason = "강제청산(LIQ)"
                    msg = f"💀 [강제 청산] 수수료 포함 증거금이 모두 소진되었습니다."
                    print(msg)
                    await send_telegram_msg(msg)
                    
                elif roe_pct >= TARGET_ROE:
                    balance = margin + gross_pnl - exit_fee
                    close_reason = "익절(TP)"
                    msg = (f"✅ [{pos_type} 목표가 도달! 익절]\n"
                           f"💰 청산가: {current_price:.2f}\n"
                           f"💸 낸 수수료 총합: {entry_fee + exit_fee:.2f} USDT\n"
                           f"💵 순수익: +{net_trade_pnl:.2f} USDT (찐 수익률: +{roe_pct*100:.2f}%)\n"
                           f"💳 현재 잔고: {balance:.2f} USDT")
                    print(msg)
                    await send_telegram_msg(msg)
                    
                elif roe_pct <= STOPLOSS_ROE:
                    balance = margin + gross_pnl - exit_fee
                    close_reason = "손절(SL)"
                    msg = (f"❌ [{pos_type} 손절가 이탈! 손절]\n"
                           f"💰 청산가: {current_price:.2f}\n"
                           f"💸 낸 수수료 총합: {entry_fee + exit_fee:.2f} USDT\n"
                           f"💵 순손실: {net_trade_pnl:.2f} USDT (찐 수익률: {roe_pct*100:.2f}%)\n"
                           f"💳 현재 잔고: {balance:.2f} USDT")
                    print(msg)
                    await send_telegram_msg(msg)

                if close_reason:
                    trade_record = {
                        "진입시간": entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                        "청산시간": current_time.strftime('%Y-%m-%d %H:%M:%S'),
                        "포지션": pos_type, # 🌟 엑셀에 LONG/SHORT 기록
                        "레버리지": LEVERAGE,
                        "진입가": round(entry_price, 2),
                        "청산가": round(current_price, 2),
                        "초기원금(USDT)": round(initial_investment, 2),
                        "총수수료(USDT)": round(entry_fee + exit_fee, 2),
                        "순손익(USDT)": round(net_trade_pnl, 2) if close_reason != "강제청산(LIQ)" else -round(initial_investment, 2),
                        "최종ROE(%)": round(roe_pct * 100, 2) if close_reason != "강제청산(LIQ)" else -100.0,
                        "종료사유": close_reason,
                        "최종잔고(USDT)": round(balance, 2)
                    }
                    save_trade_history(trade_record)
                    position = None
                    
                    if close_reason == "강제청산(LIQ)":
                        break 

            now = datetime.now()
            next_run = now.replace(second=0, microsecond=0) + timedelta(minutes=3 - (now.minute % 3))
            sleep_seconds = (next_run - now).total_seconds()
            
            await asyncio.sleep(sleep_seconds)
            
        except Exception as e:
            print(f"⚠️ 봇 실행 중 에러 발생: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_bot())