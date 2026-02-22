import os
import sys # 🌟 추가
import traceback
import importlib
import pandas as pd
import vectorbt as vbt
from openai import OpenAI
from dotenv import load_dotenv

# 🌟 경로 설정 추가: 상위 폴더(src)를 인식하게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        df = add_indicators(fetch_historical_data(limit=1000))
        
        # 동적 로드 및 리로드
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
            
        res = s_cand.apply_strategy(df)
        
        if not isinstance(res, tuple) or len(res) != 2:
            return False, "반환 형식이 (df, params_dict)가 아닙니다."
        return True, "Success"
    except Exception:
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """AI를 이용해 코드를 개선하고 에러 발생 시 스스로 수정"""
    strategy_path = "src/strategies/strategy.py"
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    system_prompt = "너는 최고 수준의 가상화폐 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록(```python ... ```)만 출력해."
    
    # 🌟 프롬프트 개선: '시퀀스(순서)' 중심의 로직 지시 (0회 거래 방지)
    user_prompt = f"""
    아래 매매 전략 코드(`strategy.py`)를 개선해줘.
    ```python
    {current_code}
    ```
    [개선 지침]
    1. **진입 로직 (핵심)**: 단순히 한 캔들에서 동시에 일어나는 조건이 아니라 '흐름'을 타야 해.
       - Long: 과거 10캔들 내에 가격이 VAL 아래로 내려간 적이 있고(rolling.max > 0), 현재 캔들이 VAL 위로 상향 돌파할 때 진입.
       - Short: 과거 10캔들 내에 가격이 VAH 위로 올라간 적이 있고, 현재 캔들이 VAH 아래로 하향 돌파할 때 진입.
    2. **필터**: CVD가 CVD_Signal을 골든크로스(Long) / 데드크로스(Short) 하는 수급 반전을 필수로 확인해.
    3. **추세 방어**: ADX가 25 이상이면서 가격이 EMA_200과 너무 멀리(예: 2% 이상) 떨어져 있을 때는 역추세 진입을 자제해.
    4. **거래 빈도**: 필터가 너무 빡빡해서 거래가 0회면 안 돼. 수익이 안 나더라도 일단 거래가 발생하도록 유연하게 짜줘.
    5. **반환 형식**: 반드시 `return df, params` 형태여야 함.
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
        
        candidate_path = "src/strategies/strategy_candidate.py"
        with open(candidate_path, "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        is_valid, error_msg = test_code_syntax()
        if is_valid:
            print("✅ AI 코드 문법 및 로직 테스트 통과!")
            return new_code_clean
        else:
            print(f"⚠️ 에러 발생, AI에게 수정을 재요청합니다...")
            user_prompt += f"\n\n[이전 코드 에러 로그]:\n{error_msg}\n위 에러를 해결해서 다시 짜줘."
            
    return None

def run_backtest_and_chart():
    """후보 전략 검증 및 상세 로그 출력"""
    print("📊 10일 데이터 백테스트 및 리포트 생성 중...")
    df = add_indicators(fetch_historical_data(limit=5000))
    
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df, params = s_cand.apply_strategy(df)
    
    # 🌟 추가: 신호 개수 실시간 디버깅 로그
    l_count = df['Long_Signal'].sum()
    s_count = df['Short_Signal'].sum()
    print(f"🔍 [디버깅] 포착된 신호 - Long: {l_count}회, Short: {s_count}회")
    
    if l_count + s_count == 0:
        print("⚠️ 경고: 거래 신호가 0회입니다. AI가 너무 빡빡한 조건을 생성했을 가능성이 높습니다.")

    # 백테스트 실행
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df.get('Long_Signal', False), 
        short_entries=df.get('Short_Signal', False),
        tp_stop=params.get('tp', 0.02),
        sl_stop=params.get('sl', 0.015), 
        fees=0.0005, 
        freq='3m',
        leverage=10,        # 🌟 10배 레버리지 추가
        leverage_fixed=True # 레버리지 고정
    )
    
    report_dir = "data/reports"
    os.makedirs(report_dir, exist_ok=True)
    pf.plot().write_image(f"{report_dir}/report.png", width=1200, height=800)
    
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res_pct, count = run_backtest_and_chart()
        print(f"📊 백테스트 결과: 수익률 {res_pct:.2f}%, 거래 횟수 {count}회")
        
        with open("data/reports/report_stats.txt", "w") as f:
            f.write(f"{res_pct:.2f},{count}")
        
        print(f"🎉 진화 작업 완료!")