import os
import traceback
import importlib
import pandas as pd
import vectorbt as vbt
from openai import OpenAI
from dotenv import load_dotenv
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

def test_code_syntax():
    try:
        df = add_indicators(fetch_historical_data(limit=1000))
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        res = s_cand.apply_strategy(df)
        # 반환 형식이 (df, dict)인지 엄격히 체크
        if not isinstance(res, tuple) or len(res) != 2:
            raise ValueError("반환 형식이 반드시 (df, params) 튜플이어야 합니다.")
        return True, "Success"
    except Exception as e:
        return False, traceback.format_exc()

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
    1. 파일 상단에 반드시 `import pandas_ta as ta`와 `import numpy as np`를 포함해.
    2. 함수 이름은 `apply_strategy(df, ema_len=30)`으로 작성해.
    3. 마지막 반환 값은 반드시 `return df, {{'tp': 0.02, 'sl': 0.015}}` 형태여야 해.
    4. CVD, ADX, EMA_200 지표를 사용하여 리스크 필터를 강화해.
    """
    
    for attempt in range(1, 4):
        print(f"🤖 AI 전략 진화 시도 ({attempt}/3)...")
        response = client.chat.completions.create(model="solar-pro3", messages=[{"role": "user", "content": user_prompt}], temperature=0.2)
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        with open("src/strategies/strategy_candidate.py", "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        is_valid, error_msg = test_code_syntax()
        if is_valid: return new_code_clean
        else:
            print(f"⚠️ 재수정 시도 중..."); user_prompt += f"\n\n오류 내용: {error_msg}"
    return None

def run_backtest_and_chart():
    df = add_indicators(fetch_historical_data(limit=5000))
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df, d_params = s_cand.apply_strategy(df)
    pf = vbt.Portfolio.from_signals(df['close'], entries=df.get('Long_Signal', False), short_entries=df.get('Short_Signal', False), 
                                    tp_stop=d_params.get('tp', 0.02), sl_stop=d_params.get('sl', 0.015), fees=0.0005, slippage=0.001, freq='3m')
    pf.plot().write_image("data/reports/report.png", width=1200, height=800)
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res_pct, count = run_backtest_and_chart()
        with open("data/reports/report_stats.txt", "w") as f: f.write(f"{res_pct:.2f},{count}")