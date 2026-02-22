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

client = OpenAI(
    api_key=os.getenv('UPSTAGE_API_KEY'),
    base_url="https://api.upstage.ai/v1" 
)

def test_code_syntax():
    try:
        # 테스트는 가볍게 1000개로 진행
        df = add_indicators(fetch_historical_data(limit=1000))
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        res = s_cand.apply_strategy(df)
        return True, "Success"
    except Exception:
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    strategy_path = "src/strategies/strategy.py"
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    system_prompt = "너는 최고 수준의 가상화폐 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록(```python ... ```)만 출력해."
    
    user_prompt = f"""
    아래 매매 전략 코드를 개선해줘.
    ```python
    {current_code}
    ```
    [개선 지침 - 거래 횟수 확보 필수]
    1. **필터 완화**: 청산 구역이나 펀딩비 같은 너무 지엽적인 조건은 삭제해. 거래가 한 번도 안 일어나는 게 가장 큰 문제야.
    2. **핵심 지표**: VAL/VAH 이탈 후 복귀(Sweep)와 CVD의 수급 반전만으로도 충분히 강력해. 
    3. **추세 방어**: ADX > 25이면서 가격이 EMA_200 위에 있을 때 '숏'만 금지하는 식으로 영리하게 짜줘.
    4. **형식**: 반환값은 반드시 True/False(Boolean) 시리즈여야 해. 숫자를 곱하지 마.
    """
    
    for attempt in range(1, 4):
        print(f"🤖 AI 전략 진화 시도 ({attempt}/3)...")
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.3
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
            user_prompt += f"\n\n에러 수정 요청:\n{error_msg}"
            
    return None

def run_backtest_and_chart():
    # 🌟 보스 요청대로 10일치(5000캔들)로 변경
    print("📊 10일 분량 데이터로 검증 및 차트 생성 중...")
    df = add_indicators(fetch_historical_data(limit=5000))
    
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
        print(f"🎉 진화 완료! 10일 수익률: {res_pct:.2f}% (거래 횟수: {count})")