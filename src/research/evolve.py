import os, sys, traceback, importlib
import pandas as pd
import vectorbt as vbt
from openai import OpenAI
from dotenv import load_dotenv
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

def test_strategy_utility(df):
    try:
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        res = s_cand.apply_strategy(df.copy())
        if res[0]['Signal'].abs().sum() == 0: return False, "신호 없음"
        return True, "Success"
    except Exception: return False, traceback.format_exc()

def generate_and_correct_strategy():
    with open(os.path.join(BASE_DIR, "strategies/strategy.py"), "r") as f: current_code = f.read()
    # 🌟 강력한 지침 추가
    prompt = f"아래 전략을 개선해. VAL/VAH/CVD 지표는 이미 있으니 중복 계산하지 마. vectorbt 사용 시 leverage 인자는 절대 금지.\n```python\n{current_code}\n```"
    
    for attempt in range(1, 4):
        resp = client.chat.completions.create(model="solar-pro3", messages=[{"role": "user", "content": prompt}])
        new_code = resp.choices[0].message.content.split("```python")[1].split("```")[0].strip()
        with open(os.path.join(BASE_DIR, "strategies/strategy_candidate.py"), "w") as f: f.write(new_code)
        if test_strategy_utility(add_indicators(fetch_historical_data(limit=1000)))[0]: return True
    return False

def run_backtest_and_chart():
    df = add_indicators(fetch_historical_data(limit=5000))
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df_res, p = s_cand.apply_strategy(df)
    # 🌟 leverage 인자 제거
    pf = vbt.Portfolio.from_signals(df_res['close'], entries=df_res['Signal']==1, short_entries=df_res['Signal']==-1, tp_stop=p['tp'], sl_stop=p['sl'], freq='3m')
    os.makedirs("data/reports", exist_ok=True)
    pf.plot().write_image("data/reports/report.png")
    return pf.total_return() * 100, pf.trades.count()