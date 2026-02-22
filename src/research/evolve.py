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

# 🌟 Upstage API 및 solar-pro3 세팅
client = OpenAI(
    api_key=os.getenv('UPSTAGE_API_KEY'),
    base_url="https://api.upstage.ai/v1" 
)

def test_code_syntax():
    """AI가 짠 코드가 에러 없이 돌아가는지 가상 테스트"""
    try:
        df = add_indicators(fetch_historical_data(limit=1000))
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        res = s_cand.apply_strategy(df)
        if not isinstance(res, tuple) or len(res) != 2:
            raise ValueError("반환 형식이 반드시 (df, params_dict) 튜플이어야 합니다.")
        return True, "Success"
    except Exception:
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """AI를 이용해 코드를 개선하고 한 달 치 데이터에 최적화"""
    strategy_path = "src/strategies/strategy.py"
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    system_prompt = "너는 최고 수준의 가상화폐 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록(```python ... ```)만 출력해."
    
    user_prompt = f"""
    아래는 현재 내 매매 전략 코드야.
    ```python
    {current_code}
    ```
    한 달(15,000캔들) 분량의 3분봉 데이터에서 수익이 잘 나도록 로직을 개선해줘.
    - 너무 많은 조건을 AND(&)로 묶으면 신호가 안 잡히니 주의해.
    - `df['ADX']`와 `df['EMA_200']`을 써서 강한 추세장에서의 역추세 진입을 영리하게 막아줘.
    - 이미 indicators.py에서 계산된 VAL, VAH, CVD, CVD_Signal, ADX, EMA_200 컬럼을 적극 활용해.
    - 반환 규격 `return df, {{'tp': 0.02, 'sl': 0.015}}`는 절대 바꾸지 마.
    """
    
    for attempt in range(1, 4):
        print(f"🤖 AI 전략 진화 시도 ({attempt}/3)...")
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        with open("src/strategies/strategy_candidate.py", "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        is_valid, error_msg = test_code_syntax()
        if is_valid:
            print("✅ 문법 테스트 통과!")
            return new_code_clean
        else:
            print(f"⚠️ 에러 발생, 재수정 시도 중...")
            user_prompt += f"\n\n네가 짜준 코드에 에러가 났어. 고쳐서 다시 짜줘:\n{error_msg}"
            
    return None

def run_backtest_and_chart():
    """15,000 캔들(한 달 치) 백테스트 및 리포트 생성"""
    print("📊 한 달 분량 데이터로 최종 검증 및 차트 생성 중...")
    df = add_indicators(fetch_historical_data(limit=15000))
    
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df, _ = s_cand.apply_strategy(df)
    
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df.get('Long_Signal', False), 
        short_entries=df.get('Short_Signal', False),
        tp_stop=0.02, 
        sl_stop=0.015, 
        fees=0.0005, 
        freq='3m'
    )
    
    os.makedirs("data/reports", exist_ok=True)
    pf.plot().write_image("data/reports/report.png", width=1200, height=800)
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res_pct, count = run_backtest_and_chart()
        with open("data/reports/report_stats.txt", "w") as f:
            f.write(f"{res_pct:.2f},{count}")
        print(f"🎉 진화 완료! 한 달 수익률: {res_pct:.2f}% (거래 횟수: {count})")