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

client = OpenAI(
    api_key=os.getenv('UPSTAGE_API_KEY'),
    base_url="https://api.upstage.ai/v1" 
)

def test_strategy_utility(df):
    """AI가 짠 전략의 기술적/논리적 결함을 자동 검증"""
    try:
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
            
        res = s_cand.apply_strategy(df.copy())
        
        if not isinstance(res, tuple) or len(res) != 2:
            return False, "반환 형식이 (df, params_dict)가 아닙니다. 반드시 튜플로 반환하세요."
        
        df_res, _ = res
        if 'Signal' not in df_res.columns:
            return False, "'Signal' 컬럼이 생성되지 않았습니다."
            
        signal_count = df_res['Signal'].abs().sum()
        if signal_count == 0:
            return False, "거래 신호가 0회입니다. 필터를 더 유연하게 조정하세요."
            
        return True, "Success"
    except Exception:
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """AI에게 '이미 있는 지표'를 활용하도록 강력하게 지시"""
    strategy_path = os.path.join(BASE_DIR, "strategies/strategy.py")
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    system_prompt = "너는 최고 수준의 가상화폐 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록만 출력해."
    
    # 🌟 강력한 제약 사항 추가 (hallucination 방지)
    user_prompt = f"""
    아래 매매 전략 코드(`strategy.py`)를 개선해줘.
    ```python
    {current_code}
    ```
    [⚠️ 필수 준수 사항 - 어길 시 실행 에러 발생]
    1. **중복 계산 절대 금지**: 'VAL', 'VAH', 'POC', 'ADX', 'RSI', 'EMA_200', 'CVD', 'CVD_Signal', 'Squeeze_On'은 이미 데이터프레임에 포함되어 있어. 절대로 `ta.adx()`나 `ta.value_area()` 등으로 다시 계산하지 말고 `df['VAL']`처럼 바로 사용해.
    2. **ADX 사용법**: ADX는 이미 계산되어 있으니 필터로만 사용해. 만약 다시 계산해야 한다면 `df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14']` 처럼 특정 컬럼을 인덱싱해야 해.
    3. **불리언 마스크**: `~` 연산 사용 전 반드시 `.astype(bool)`을 적용해.
    4. **반환 형식**: 반드시 `return df, params` 튜플 형태를 유지해.

    [개선 전략 로직]
    - 지훈의 안정화 로직 계승: 매물대 하단(VAL) 이탈 후 복귀 시 Long, 상단(VAH) 돌파 후 복귀 시 Short.
    - Squeeze_On이 False일 때(변동성 폭발 시) 진입하는 조건을 고려해봐.
    """
    
    test_df = add_indicators(fetch_historical_data(limit=1000))
    candidate_path = os.path.join(BASE_DIR, "strategies/strategy_candidate.py")
    
    for attempt in range(1, 6):
        print(f"🤖 AI 전략 진화 시도 ({attempt}/5)...")
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.3 
        )
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        with open(candidate_path, "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        is_valid, error_msg = test_strategy_utility(test_df)
        if is_valid:
            print("✅ 전략 유효성 검사 통과!")
            return new_code_clean
        else:
            print(f"⚠️ 에러 발생, 수정을 재요청합니다...")
            user_prompt += f"\n\n[이전 시도 실패 로그]:\n{error_msg}\n위 에러를 참고해서 다시 짜줘."
            
    return None

def run_backtest_and_chart():
    """후보 전략 백테스트 (leverage 인자 제거로 에러 방지)"""
    print("📊 백테스트 및 리포트 생성 중...")
    raw_df = fetch_historical_data(limit=5000)
    df = add_indicators(raw_df)
    
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df, params = s_cand.apply_strategy(df)
    
    # 🌟 vectorbt 오픈소스 버전 호환성 (leverage 삭제)
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
    
    report_dir = os.path.join(os.path.dirname(BASE_DIR), "data/reports")
    os.makedirs(report_dir, exist_ok=True)
    pf.plot().write_image(os.path.join(report_dir, "report.png"), width=1200, height=800)
    
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res_pct, count = run_backtest_and_chart()
        print(f"🎉 진화 작업 완료! 수익률: {res_pct:.2f}%")