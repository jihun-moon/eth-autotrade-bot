import os
import sys
import traceback
import importlib
import pandas as pd
import vectorbt as vbt
from openai import OpenAI
from dotenv import load_dotenv

# 🌟 경로 설정: 상위 폴더(src)를 인식하게 하여 utils, strategies를 찾을 수 있게 함
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

load_dotenv()

# Upstage Solar-Pro API 설정
client = OpenAI(
    api_key=os.getenv('UPSTAGE_API_KEY'),
    base_url="https://api.upstage.ai/v1" 
)

def test_strategy_utility(df):
    """
    AI가 짠 전략의 실효성을 테스트합니다.
    1. 문법 및 실행 에러 여부
    2. 반환 형식 준수 여부
    3. 🌟 실제 거래 신호(Signal) 발생 여부 (유연함의 핵심)
    """
    try:
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
            
        res = s_cand.apply_strategy(df.copy())
        
        # 형식 검증
        if not isinstance(res, tuple) or len(res) != 2:
            return False, "반환 형식이 (df, params_dict)가 아닙니다. 반드시 튜플로 반환하세요."
        
        df_res, _ = res
        # 거래 신호 검증: 0회면 실패로 간주하고 AI에게 다시 요청
        signal_count = df_res['Signal'].abs().sum()
        if signal_count == 0:
            return False, "생성된 전략에서 거래 신호가 0회 발생했습니다. 진입 조건을 너무 빡빡하게 짰거나 논리 오류가 있습니다. 필터를 완화해서 다시 짜주세요."
            
        return True, "Success"
    except Exception:
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """AI를 이용해 코드를 개선하고, 결과가 부적합하면 처음부터 다시 짜게 함"""
    strategy_path = os.path.join(BASE_DIR, "strategies/strategy.py")
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    system_prompt = "너는 최고 수준의 가상화폐 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록(```python ... ```)만 출력해."
    
    # 🌟 AI에게 주는 가이드라인 강화
    user_prompt = f"""
    아래 매매 전략 코드(`strategy.py`)를 처음부터 분석해서 개선해줘.
    ```python
    {current_code}
    ```
    [중요 지침]
    1. **필수 임포트**: 코드 최상단에 `import pandas as pd`, `import numpy as np`, `import pandas_ta as ta`를 반드시 포함해.
    2. **유연한 타점**: 조건이 너무 까다로우면 거래가 안 일어나. '완벽한 타점'보다 '확률 높은 타점'을 노리고, 10일간 최소 5회 이상은 거래가 발생하도록 필터를 조절해.
    3. **로직 개선**: 가격이 VAL 아래로 내려갔다 복귀할 때(Long), VAH 위로 올라갔다 복귀할 때(Short)를 핵심으로 하되, CVD 수급 반전을 확인해.
    4. **반환 형식**: 반드시 `return df, params` 형태를 지켜.
    """
    
    # 지표가 포함된 테스트용 데이터 준비
    test_df = add_indicators(fetch_historical_data(limit=1000))
    candidate_path = os.path.join(BASE_DIR, "strategies/strategy_candidate.py")
    
    for attempt in range(1, 6): # 시도 횟수를 5회로 늘려 안정성 확보
        print(f"🤖 AI 전략 유연 진화 시도 ({attempt}/5)...")
        
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.4 # 창의성과 유연성을 위해 약간 높임
        )
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        # 파일 저장
        with open(candidate_path, "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        # 🌟 실효성 테스트 실행
        is_valid, error_msg = test_strategy_utility(test_df)
        if is_valid:
            print("✅ 전략 유효성 검사 통과! (거래 신호 확인됨)")
            return new_code_clean
        else:
            print(f"⚠️ 전략 보완 필요: {error_msg}")
            # AI에게 구체적인 실패 사유를 알려주며 다시 짜게 함
            user_prompt += f"\n\n[이전 시도 실패 사유]:\n{error_msg}\n위 문제를 해결해서 다시 짜줘."
            
    return None

def run_backtest_and_chart():
    """후보 전략을 10일치 데이터로 검증하고 차트 생성"""
    print("📊 10일 데이터 백테스트 및 리포트 생성 중...")
    raw_df = fetch_historical_data(limit=5000)
    df = add_indicators(raw_df)
    
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df, params = s_cand.apply_strategy(df)
    
    l_count = df['Long_Signal'].sum() if 'Long_Signal' in df.columns else 0
    s_count = df['Short_Signal'].sum() if 'Short_Signal' in df.columns else 0
    print(f"🔍 [최종 확인] 신호 포착 - Long: {l_count}회, Short: {s_count}회")

    # 10배 레버리지 백테스트
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df.get('Long_Signal', False), 
        short_entries=df.get('Short_Signal', False),
        tp_stop=params.get('tp', 0.02),
        sl_stop=params.get('sl', 0.015), 
        fees=0.0005, 
        freq='3m',
        leverage=10,        # 🌟 10배 레버리지 반영
        leverage_fixed=True
    )
    
    report_dir = os.path.join(os.path.dirname(BASE_DIR), "data/reports")
    os.makedirs(report_dir, exist_ok=True)
    pf.plot().write_image(f"{report_dir}/report.png", width=1200, height=800)
    
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res_pct, count = run_backtest_and_chart()
        
        print(f"📊 백테스트 결과: 수익률 {res_pct:.2f}%, 거래 횟수 {count}회")
        
        # 통계 데이터 저장
        stats_file = os.path.join(os.path.dirname(BASE_DIR), "data/reports/report_stats.txt")
        with open(stats_file, "w") as f:
            f.write(f"{res_pct:.2f},{count}")
        
        print(f"🎉 진화 작업 완료!")