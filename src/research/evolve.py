import os
import traceback
import importlib
import pandas as pd
import vectorbt as vbt
import logging
from openai import OpenAI
from dotenv import load_dotenv
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

# 로깅 설정
logger = logging.getLogger("EvolveEngine")

load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

def test_code_syntax():
    """AI가 짠 코드를 임포트하여 실제로 1000행의 데이터에 적용해봄"""
    try:
        # 데이터 준비
        raw_data = fetch_historical_data(limit=1000)
        df_with_ind = add_indicators(raw_data)
        
        # 생성된 후보 전략 파일 임포트
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        
        # 실행 테스트
        res = s_cand.apply_strategy(df_with_ind)
        
        # 규격 체크
        if not isinstance(res, tuple) or len(res) != 2:
            raise ValueError("반환 형식이 반드시 (df, params_dict) 튜플이어야 합니다.")
            
        df_res, params = res
        if 'target_tp' not in df_res.columns or 'target_sl' not in df_res.columns:
            raise KeyError("전략 결과 데이터프레임에 'target_tp'와 'target_sl' 컬럼이 반드시 포함되어야 합니다.")
            
        return True, "Success"
    except Exception as e:
        # 상세한 에러 내용을 반환하여 AI가 자가 수정하게 함
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    strategy_path = "src/strategies/strategy.py"
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    # AI가 헛발질(ta.val() 등) 하지 않도록 지시사항을 아주 구체적으로 보강
    user_prompt = f"""
    아래 매매 전략 코드를 개선해줘.
    ```python
    {current_code}
    ```
    
    [⚠️ 매우 중요: 기술적 제약 사항]
    1. 파일 상단에 `import pandas_ta as ta`와 `import numpy as np`를 반드시 포함해.
    2. 데이터프레임에는 이미 'CVD', 'CVD_Signal', 'ADX', 'EMA_200', 'VAL', 'VAH' 컬럼이 있어. 
       - 절대로 ta.val(), ta.vah(), ta.cvd() 같은 존재하지 않는 함수를 호출하지 마.
       - 이미 존재하는 컬럼명을 그대로 활용해.
    3. 반드시 `target_tp`와 `target_sl` 컬럼을 ATR 기반으로 생성해서 데이터프레임에 넣어.
    4. 함수의 마지막은 반드시 `return df, {{'tp': last_tp, 'sl': last_sl}}` 형태여야 해.
    """
    
    for attempt in range(1, 4):
        print(f"\n🤖 AI 전략 진화 시도 ({attempt}/3)...")
        response = client.chat.completions.create(
            model="solar-pro3", 
            messages=[{"role": "user", "content": user_prompt}], 
            temperature=0.2
        )
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        # 파일 저장
        with open("src/strategies/strategy_candidate.py", "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        # 문법 및 규격 검증
        is_valid, error_msg = test_code_syntax()
        
        if is_valid: 
            print("✅ 문법 검증 통과! 백테스트를 시작합니다.")
            return new_code_clean
        else: 
            # 🌟 지훈님이 오류를 볼 수 있게 화면에 출력
            print(f"❌ 검증 실패 (Attempt {attempt}):\n{error_msg}")
            print(f"⚠️ AI에게 재수정을 요청합니다...")
            user_prompt += f"\n\n이전 코드에서 다음 오류가 발생했어. 이 오류를 해결해서 다시 짜줘:\n{error_msg}"
            
    print("🚨 3회 시도 모두 실패했습니다.")
    return None

def run_backtest_and_chart():
    print("📈 백테스트 리포트 생성 중...")
    df = add_indicators(fetch_historical_data(limit=5000))
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    
    df, d_params = s_cand.apply_strategy(df)
    
    # 컬럼 기반 동적 백테스트
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df.get('Long_Signal', False), 
        short_entries=df.get('Short_Signal', False), 
        tp_stop=df['target_tp'], 
        sl_stop=df['target_sl'], 
        fees=0.0005, 
        slippage=0.001, 
        freq='3m'
    )
    
    os.makedirs("data/reports", exist_ok=True)
    pf.plot().write_image("data/reports/report.png", width=1200, height=800)
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    new_strategy = generate_and_correct_strategy()
    if new_strategy:
        res_pct, count = run_backtest_and_chart()
        with open("data/reports/report_stats.txt", "w") as f: 
            f.write(f"{res_pct:.2f},{count}")