import os
import traceback
import importlib
import pandas as pd
import vectorbt as vbt
import shutil  # 🌟 파일 복사를 위해 추가
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
    """AI가 짠 코드가 에러 없이 돌아가는지 가상 테스트"""
    try:
        # 문법 테스트 데이터도 2000개 정도로 확보 (지표 계산 안정성)
        df = add_indicators(fetch_historical_data(limit=2000))
        
        # 동적 로드 및 리로드
        if 'strategies.strategy_candidate' in importlib.import_module('sys').modules:
            import strategies.strategy_candidate as s_cand
            importlib.reload(s_cand)
        else:
            import strategies.strategy_candidate as s_cand
            
        res = s_cand.apply_strategy(df)
        if not isinstance(res, tuple) or len(res) != 2:
            return False, "반환 형식이 (df, params_dict)가 아닙니다."
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
    [개선 지침]
    1. VAL/VAH 이탈 후 복귀와 CVD 수급 반전을 활용해.
    2. ADX와 EMA_200으로 추세 역행을 방어해.
    3. 거래가 너무 안 잡히면 수익이 안 나니 필터를 너무 빡빡하게 짜지 마.
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
            print(f"⚠️ 에러 발생, 다시 시도 중...")
            user_prompt += f"\n\n에러 수정 요청:\n{error_msg}"
            
    return None

def run_backtest_and_chart():
    print("📊 10일 분량 데이터로 검증 및 차트 생성 중...")
    df = add_indicators(fetch_historical_data(limit=5000)) # 10일치
    
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df, params = s_cand.apply_strategy(df)
    
    # 신호가 아예 없는지 체크
    if 'Long_Signal' not in df.columns or df['Long_Signal'].sum() == 0:
        print("⚠️ 주의: 롱 신호가 하나도 없습니다.")

    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df.get('Long_Signal', False), 
        short_entries=df.get('Short_Signal', False),
        tp_stop=params.get('tp', 0.02), # 전략이 준 파라미터 사용
        sl_stop=params.get('sl', 0.015), 
        fees=0.0005, 
        freq='3m'
    )
    
    os.makedirs("data/reports", exist_ok=True)
    pf.plot().write_image("data/reports/report.png", width=1200, height=800)
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res_pct, count = run_backtest_and_chart()
        
        # 🌟 자율 배포 로직: 수익률 2% 이상 시 자동 반영
        if res_pct >= 2.0 and count >= 5:
            print(f"🚀 성적 우수({res_pct:.2f}%)! 전략을 즉시 실전에 반영합니다.")
            shutil.copy("src/strategies/strategy_candidate.py", "src/strategies/strategy.py")
        
        with open("data/reports/report_stats.txt", "w") as f:
            f.write(f"{res_pct:.2f},{count}")
        print(f"🎉 진화 완료! 10일 수익률: {res_pct:.2f}% (거래 횟수: {count})")