import os
import sys
import traceback
import importlib
import pandas as pd
import vectorbt as vbt
from openai import OpenAI
from dotenv import load_dotenv

# 🌟 경로 설정: 파일 위치(src/research)에 상관없이 프로젝트 루트와 src를 정확히 인식
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# 통합된 유틸리티 임포트
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

load_dotenv()

client = OpenAI(
    api_key=os.getenv('UPSTAGE_API_KEY'),
    base_url="https://api.upstage.ai/v1" 
)

def test_strategy_utility(df):
    """생성된 AI 전략의 기술적/논리적 결함을 자동 검증"""
    try:
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
            
        res = s_cand.apply_strategy(df.copy())
        
        # 1. 반환 형식 검증
        if not isinstance(res, tuple) or len(res) != 2:
            return False, "반환 형식이 (df, params_dict)가 아닙니다. 반드시 튜플로 반환하세요."
        
        df_res, _ = res
        # 2. 거래 신호 존재 여부 검증 (유연함 확보)
        if 'Signal' not in df_res.columns:
            return False, "'Signal' 컬럼이 데이터프레임에 존재하지 않습니다."
            
        signal_count = df_res['Signal'].abs().sum()
        if signal_count == 0:
            return False, "거래 신호가 0회입니다. 진입 필터(ADX, RSI 등)를 더 유연하게 조정하세요."
            
        return True, "Success"
    except Exception:
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """AI에게 안정화 버전의 로직을 기반으로 개선을 명령"""
    strategy_path = os.path.join(BASE_DIR, "strategies/strategy.py")
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    system_prompt = "너는 최고 수준의 가상화폐 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록(```python ... ```)만 출력해."
    
    # 🌟 예전 안정화 버전의 핵심 철학을 AI에게 주입
    user_prompt = f"""
    아래 매매 전략 코드(`strategy.py`)를 개선해줘.
    ```python
    {current_code}
    ```
    [개선 지침 - 지훈의 안정화 로직 계승]
    1. **다이버전스 강화**: `low.rolling(window=5).min()`을 활용해 저점이 갱신될 때 RSI가 상승하는 '상승 다이버전스'를 핵심 신호로 삼아.
    2. **매물대 활용**: `VAL`(Value Area Low) 아래에서 위로 복귀할 때 Long, `VAH` 위에서 아래로 복귀할 때 Short 진입해.
    3. **수급 필터**: `CVD`가 `CVD_Signal`을 돌파하는 수급 반전을 필수로 확인해.
    4. **추세 방어**: `ADX`가 25 이상일 때의 역추세 진입은 자제하되, 거래가 너무 안 터지면 이 수치를 조절해.

    [기술적 필수 규칙]
    - 반드시 `import pandas_ta as ta`, `import numpy as np`를 포함할 것.
    - 불리언 연산 시 `astype(bool)` 적용: `(~df['col'].astype(bool))`.
    - 넘파이 배열 처리: `pd.Series(np.where(...), index=df.index).ffill()`.
    """
    
    test_df = add_indicators(fetch_historical_data(limit=1000))
    candidate_path = os.path.join(BASE_DIR, "strategies/strategy_candidate.py")
    
    for attempt in range(1, 6):
        print(f"🤖 AI 전략 진화 시도 ({attempt}/5)...")
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.4 
        )
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        with open(candidate_path, "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        is_valid, error_msg = test_strategy_utility(test_df)
        if is_valid:
            print("✅ 전략 유효성 검사 통과! (거래 신호 확인됨)")
            return new_code_clean
        else:
            print(f"⚠️ 보완 필요: {error_msg}")
            user_prompt += f"\n\n[이전 시도 실패 사유]:\n{error_msg}\n이 에러를 고치고 전략을 더 유연하게 다시 짜줘."
            
    return None

def run_backtest_and_chart():
    """후보 전략의 수익률을 1배율 기준으로 검증 (실전은 10배 적용)"""
    print("📊 백테스트 및 리포트 생성 중...")
    raw_df = fetch_historical_data(limit=5000)
    df = add_indicators(raw_df)
    
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df, params = s_cand.apply_strategy(df)
    
    l_count = df['Long_Signal'].sum() if 'Long_Signal' in df.columns else 0
    s_count = df['Short_Signal'].sum() if 'Short_Signal' in df.columns else 0
    print(f"🔍 [신호 통계] Long: {l_count}회, Short: {s_count}회")

    # 🌟 vectorbt 호환성: leverage 제거, 실전은 main.py에서 10배 처리
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df.get('Long_Signal', False), 
        short_entries=df.get('Short_Signal', False),
        tp_stop=params.get('tp', 0.02),
        sl_stop=params.get('sl', 0.015), 
        fees=0.0005, 
        freq='3m',
        init_cash=10000 
    )
    
    # 루트 폴더의 data/reports 경로에 저장
    report_dir = os.path.join(os.path.dirname(BASE_DIR), "data/reports")
    os.makedirs(report_dir, exist_ok=True)
    pf.plot().write_image(os.path.join(report_dir, "report.png"), width=1200, height=800)
    
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res_pct, count = run_backtest_and_chart()
        print(f"📊 백테스트 결과: 수익률 {res_pct:.2f}%, 거래 {count}회")
        
        report_dir = os.path.join(os.path.dirname(BASE_DIR), "data/reports")
        with open(os.path.join(report_dir, "report_stats.txt"), "w") as f:
            f.write(f"{res_pct:.2f},{count}")
        print(f"🎉 진화 작업 완료!")