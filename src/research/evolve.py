import os
import sys
import traceback
import importlib
import pandas as pd
import vectorbt as vbt
from openai import OpenAI
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

def test_strategy_utility(df):
    try:
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        res = s_cand.apply_strategy(df.copy())
        if not isinstance(res, tuple) or len(res) != 2: return False, "반환 형식이 튜플이 아닙니다."
        if res[0]['Signal'].abs().sum() == 0: return False, "거래 신호가 발생하지 않았습니다."
        return True, "Success"
    except Exception: return False, traceback.format_exc()

def generate_and_correct_strategy():
    strategy_path = os.path.join(BASE_DIR, "strategies/strategy.py")
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    system_prompt = "너는 최고 수준의 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록만 출력해."
    user_prompt = f"""
    아래 전략(`strategy.py`)을 개선해줘.
    ```python
    {current_code}
    ```
    [규칙]
    1. 'VAL', 'VAH', 'CVD', 'ADX', 'Squeeze_On'은 이미 indicators.py에 있으니 절대 다시 계산하지 마.
    2. 불리언 마스크 적용 시 .astype(bool) 필수.
    3. vectorbt 백테스트 시 leverage 인자는 절대 사용 금지.
    """
    
    test_df = add_indicators(fetch_historical_data(limit=1000))
    candidate_path = os.path.join(BASE_DIR, "strategies/strategy_candidate.py")
    
    for attempt in range(1, 6):
        print(f"🤖 AI 전략 진화 시도 ({attempt}/5)...")
        response = client.chat.completions.create(model="solar-pro3", messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        with open(candidate_path, "w", encoding="utf-8") as f: f.write(new_code_clean)
        is_valid, error_msg = test_strategy_utility(test_df)
        if is_valid: return new_code_clean
        user_prompt += f"\n\n[이전 실패 로그]:\n{error_msg}\n고쳐서 다시 짜줘."
    return None

def run_backtest_and_chart():
    df = add_indicators(fetch_historical_data(limit=5000))
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df_res, params = s_cand.apply_strategy(df)
    
    pf = vbt.Portfolio.from_signals(df_res['close'], entries=df_res.get('Long_Signal', False), 
                                   short_entries=df_res.get('Short_Signal', False), 
                                   tp_stop=params['tp'], sl_stop=params['sl'], freq='3m', init_cash=10000)
    
    report_dir = os.path.join(os.path.dirname(BASE_DIR), "data/reports")
    os.makedirs(report_dir, exist_ok=True)
    pf.plot().write_image(os.path.join(report_dir, "report.png"))
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res, count = run_backtest_and_chart()
        print(f"📊 진화 완료! 수익률: {res:.2f}%")