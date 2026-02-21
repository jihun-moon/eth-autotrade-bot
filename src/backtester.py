import pandas as pd
import os
from indicators import add_indicators
from strategy import apply_strategy

def run_paper_trading(df, initial_balance=10000.0):
    print(f"💸 스마트머니 모의 투자 시작! 초기 자본: {initial_balance:,.2f} USDT\n")
    
    balance = initial_balance
    position = 0.0
    entry_price = 0.0
    
    # 전략적 익절/손절 라인 변수
    tp_price = 0.0 # Take Profit (목표가)
    sl_price = 0.0 # Stop Loss (손절가)
    
    fee_rate = 0.001 
    
    for timestamp, row in df.iterrows():
        current_price = row['close']
        
        # 1. 롱 진입 로직
        if position == 0.0 and row['Long_Signal'] == True:
            invest_amount = balance
            position = (invest_amount * (1 - fee_rate)) / current_price
            entry_price = current_price
            balance = 0.0
            
            # 🌟 [핵심 변경] 파인스크립트 룰에 따른 목표가/손절가 세팅
            # 손절가: 직전 10캔들 중 가장 낮았던 꼬리(Swing Low)보다 살짝(0.1%) 아래
            sl_price = row['Swing_Low'] * 0.999 
            
            # 목표가: 파인스크립트 피보나치 레벨 1.0 적용 (파동 크기만큼 위로)
            swing_range = row['Swing_High'] - row['Swing_Low']
            tp_price = entry_price + (swing_range * 1.0) 
            
            print(f"🟢 [매수 진입] {timestamp}")
            print(f"   - 진입가: {entry_price:,.2f} USDT | 매수 수량: {position:.4f} ETH")
            print(f"   - 🎯 목표가(TP): {tp_price:,.2f} | 🛡️ 손절가(SL): {sl_price:,.2f}")
            
        # 2. 청산 로직 (스마트 엑시트)
        elif position > 0.0:
            trade_result = ""
            
            # 목표가 도달 시 (익절)
            if current_price >= tp_price:
                trade_result = "익절 🎉 (피보나치 1.0 도달)"
            # 손절가 이탈 시 (직전 바닥 깨짐)
            elif current_price <= sl_price:
                trade_result = "손절 💧 (구조물 바닥 이탈)"
                
            # 청산 실행
            if trade_result != "":
                sell_amount = position * current_price * (1 - fee_rate)
                profit_rate = (current_price - entry_price) / entry_price
                balance += sell_amount
                
                print(f"🔴 [{trade_result}] {timestamp}")
                print(f"   - 청산가: {current_price:,.2f} USDT | 📈 수익률: {profit_rate*100:.2f}%")
                print(f"   - 💰 현재 잔고: {balance:,.2f} USDT\n")
                
                position = 0.0
                entry_price = 0.0
                tp_price = 0.0
                sl_price = 0.0

    final_value = balance if position == 0.0 else balance + (position * df.iloc[-1]['close'] * (1 - fee_rate))
    total_return = ((final_value - initial_balance) / initial_balance) * 100
    
    print("="*40)
    print(f"📊 [v2.0 스마트 모의 투자 성적표]")
    print(f"최종 금액: {final_value:,.2f} USDT")
    print(f"총 수익률: {total_return:.2f}%")
    print("="*40)

if __name__ == "__main__":
    file_path = '../data/eth_3m_historical.csv' if os.path.exists('../data/eth_3m_historical.csv') else 'data/eth_3m_historical.csv'
    if os.path.exists(file_path):
        raw_df = pd.read_csv(file_path, index_col='timestamp', parse_dates=True)
        run_paper_trading(apply_strategy(add_indicators(raw_df)))
    else:
        print("❌ CSV 파일 없음.")