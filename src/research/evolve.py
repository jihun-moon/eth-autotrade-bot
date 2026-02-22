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
    """AI가 짠 코드가 에러 없이 돌아가는지 가상 테스트"""
    try:
        df = add_indicators(fetch_historical_data(limit=1000))
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        
        # [수정] 반환값을 변수 하나(res)로 받아 구조를 체크 (안정적)
        res = s_cand.apply_strategy(df)
        if not isinstance(res, tuple) or len(res) != 2:
            raise ValueError("반환 형식이 반드시 (df, params) 튜플이어야 합니다.")
        return True, "Success"
    except Exception as e:
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    strategy_path = "src/strategies/strategy.py"
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    system_prompt = "너는 최고 수준의 가상화폐 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록(```python ... ```)만 출력해."
    
    user_prompt = f"""
    아래는 현재 내 매매 전략 코드야.
    ```python
    {current_code}
    ```
    이 코드를 개선해서 새로운 전략을 짜줘.
    
    [💡 필수 준수 사항]
    1. 파일 맨 위에 반드시 `import pandas_ta as ta` 를 포함해.
    2. 함수 이름은 반드시 `apply_strategy(df, ema_len=30)`으로 유지해. (매우 중요)
    3. 함수의 마지막 반환 값은 반드시 `return df, {{'tp': 0.02, 'sl': 0.015}}` 와 같이 데이터프레임과 설정값 딕셔너리를 포함한 튜플 형태여야 해.
    4. 리스크 필터링(ADX, EMA_200)을 강화해줘.
    """
    
    for attempt in range(1, 4):
        print(f"🤖 AI 전략 진화 시도 ({attempt}/3)...")
        response = client.chat.completions.create(model="solar-pro3", messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], temperature=0.2)
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        with open("src/strategies/strategy_candidate.py", "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        is_valid, error_msg = test_code_syntax()
        if is_valid: return new_code_clean
        else:
            print(f"⚠️ 에러 발생. 재수정 시도 중..."); user_prompt += f"\n\n오류: {error_msg}"
    return None

def run_backtest_and_chart():
    df = add_indicators(fetch_historical_data(limit=5000))
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    
    # [수정] 반환된 동적 파라미터(d_params)를 백테스트에 반영
    df, d_params = s_cand.apply_strategy(df)
    
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df.get('Long_Signal', False), 
        short_entries=df.get('Short_Signal', False), 
        tp_stop=d_params.get('tp', 0.02), 
        sl_stop=d_params.get('sl', 0.015), 
        fees=0.0005, 
        slippage=0.001, 
        freq='3m'
    )
    
    output_image = "data/reports/report.png"
    pf.plot().write_image(output_image, width=1200, height=800)
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res_pct, count = run_backtest_and_chart()
        with open("data/reports/report_stats.txt", "w") as f: f.write(f"{res_pct:.2f},{count}")