import os
import traceback
import importlib
import pandas as pd
import vectorbt as vbt
import numpy as np
import logging
from openai import OpenAI
from dotenv import load_dotenv
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

logging.basicConfig(level=logging.ERROR)
load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

def test_code_syntax():
    try:
        df = add_indicators(fetch_historical_data(limit=1000))
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        res = s_cand.apply_strategy(df)
        if not isinstance(res, tuple) or len(res) != 2:
            raise ValueError("반환 형식이 (df, params_dict) 튜플이어야 합니다.")
        return True, "Success"
    except Exception:
        return False, traceback.format_exc()

def find_best_params(df_ind):
    """생성된 로직에 대해 최고의 수익률을 내는 수치(TP/SL/EMA)를 강제로 찾아냄"""
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    
    ema_list = [20, 30, 50]
    tp_mults = [1.5, 2.0, 2.5, 3.0]
    sl_mults = [1.0, 1.5, 2.0]
    
    best_ret = -np.inf
    best_params = {'ema': 30, 'tp': 2.0, 'sl': 1.5}
    
    print("🔎 새 로직에 대한 최적의 수치 조합 탐색 중...")
    
    for ema in ema_list:
        # 전략 적용 (EMA 변경)
        df_temp, _ = s_cand.apply_strategy(df_ind.copy(), ema_len=ema)
        
        for tp in tp_mults:
            for sl in sl_mults:
                # 동적 TP/SL 컬럼 재계산 (최적화 루프)
                target_tp = (df_temp['ATR'] * tp / df_temp['close']).fillna(0.02)
                target_sl = (df_temp['ATR'] * sl / df_temp['close']).fillna(0.015)
                
                pf = vbt.Portfolio.from_signals(
                    df_temp['close'],
                    entries=df_temp.get('Long_Signal', False),
                    short_entries=df_temp.get('Short_Signal', False),
                    tp_stop=target_tp,
                    sl_stop=target_sl,
                    fees=0.0005, freq='3m'
                )
                
                total_ret = pf.total_return()
                if total_ret > best_ret:
                    best_ret = total_ret
                    best_params = {'ema': ema, 'tp_mult': tp, 'sl_mult': sl}
    
    print(f"🏆 최적 수치 발견: EMA {best_params['ema']}, TP {best_params['tp_mult']}배, SL {best_params['sl_mult']}배 (수익률: {best_ret*100:.2f}%)")
    return best_params

def generate_and_correct_strategy():
    strategy_path = "src/strategies/strategy.py"
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    user_prompt = f"""
    아래 매매 전략 코드를 개선해줘.
    ```python
    {current_code}
    ```
    [💡 필수 준수 사항]
    1. 반드시 `target_tp`와 `target_sl` 컬럼을 ATR 기반으로 생성해. (배수는 변수로 처리)
    2. CVD, ADX, EMA_200, VAL, VAH 컬럼을 활용해 필터를 강화해.
    3. 함수의 인자로 `ema_len`, `tp_mult`, `sl_mult`를 받을 수 있게 설계해.
    4. 마지막 반환 값은 `return df, {{'tp': last_tp, 'sl': last_sl}}` 형태여야 해.
    """
    
    for attempt in range(1, 4):
        print(f"\n🤖 AI 전략 진화 시도 ({attempt}/3)...")
        response = client.chat.completions.create(model="solar-pro3", messages=[{"role": "user", "content": user_prompt}], temperature=0.2)
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        with open("src/strategies/strategy_candidate.py", "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        is_valid, error_msg = test_code_syntax()
        if is_valid: return new_code_clean
        else: print(f"❌ 검증 실패: {error_msg}"); user_prompt += f"\n\n오류 해결 요망: {error_msg}"
    return None

def run_backtest_and_chart():
    # 5,000캔들 데이터 수집
    df = add_indicators(fetch_historical_data(limit=5000))
    
    # 🌟 [핵심] 수치 최적화 실행
    best = find_best_params(df.copy())
    
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    
    # 최적화된 수치로 최종 전략 적용
    # (AI가 만든 apply_strategy가 tp_mult 등을 인자로 받도록 설계됨)
    try:
        df, _ = s_cand.apply_strategy(df, ema_len=best['ema'])
        # 최적화된 배수로 컬럼 업데이트
        df['target_tp'] = (df['ATR'] * best['tp_mult'] / df['close']).fillna(0.02)
        df['target_sl'] = (df['ATR'] * best['sl_mult'] / df['close']).fillna(0.015)
    except:
        # AI가 인자 설계를 안했을 경우 대비 기본 실행
        df, _ = s_cand.apply_strategy(df)

    pf = vbt.Portfolio.from_signals(
        df['close'], entries=df.get('Long_Signal', False), short_entries=df.get('Short_Signal', False),
        tp_stop=df['target_tp'], sl_stop=df['target_sl'], fees=0.0005, slippage=0.001, freq='3m'
    )
    
    os.makedirs("data/reports", exist_ok=True)
    pf.plot().write_image("data/reports/report.png", width=1200, height=800)
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res_pct, count = run_backtest_and_chart()
        with open("data/reports/report_stats.txt", "w") as f: f.write(f"{res_pct:.2f},{count}")