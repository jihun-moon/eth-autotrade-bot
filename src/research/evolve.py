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

# 로깅 설정 (에러만 조용히 출력)
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("EvolveEngine")

load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

def test_code_syntax():
    """AI가 짠 코드를 임포트하여 실제로 1000행의 데이터에 적용해봄"""
    try:
        # 데이터 준비 (indicators.py에서 계산된 지표 포함)
        raw_data = fetch_historical_data(limit=1000)
        df_with_ind = add_indicators(raw_data)
        
        # 생성된 후보 전략 파일 임포트 및 강제 리로드
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        
        # 실행 테스트
        res = s_cand.apply_strategy(df_with_ind)
        
        # 규격 체크: 반환 형식이 튜플(df, dict)인지 확인
        if not isinstance(res, tuple) or len(res) != 2:
            raise ValueError("반환 형식이 반드시 (df, params_dict) 튜플이어야 합니다.")
            
        df_res, params = res
        # 필수 컬럼 존재 여부 체크
        required_cols = ['target_tp', 'target_sl', 'Long_Signal', 'Short_Signal']
        for col in required_cols:
            if col not in df_res.columns:
                raise KeyError(f"전략 결과에 '{col}' 컬럼이 누락되었습니다. 반드시 포함해야 합니다.")
            
        return True, "Success"
    except Exception as e:
        # 상세한 에러 내용을 반환하여 AI가 자가 수정하게 함
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    strategy_path = "src/strategies/strategy.py"
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    # AI에게 줄 프롬프트 강화: 예시 코드를 주어 규격 외 이탈 방지
    user_prompt = f"""
    아래 매매 전략 코드를 개선해줘.
    ```python
    {current_code}
    ```
    
    [⚠️ 필수 준수 사항 - 미준수 시 백테스트 실패]
    1. 파일 상단에 `import pandas_ta as ta`와 `import numpy as np`를 반드시 포함해.
    2. 데이터프레임에는 이미 'CVD', 'CVD_Signal', 'ADX', 'EMA_200', 'VAL', 'VAH' 컬럼이 계산되어 있어.
       - 절대로 ta.val(), ta.vah() 같이 없는 함수를 호출하지 말고 이미 있는 컬럼명을 그대로 사용해.
    3. 반드시 아래 코드를 함수 내부에 포함해서 ATR 기반 동적 TP/SL 컬럼을 생성해:
       df['target_tp'] = (df['ATR'] * 2.0 / df['close']).fillna(0.02)
       df['target_sl'] = (df['ATR'] * 1.5 / df['close']).fillna(0.015)
    4. 함수의 마지막은 반드시 아래 형태여야 해:
       last_tp = df['target_tp'].iloc[-1]
       last_sl = df['target_sl'].iloc[-1]
       return df, {{'tp': last_tp, 'sl': last_sl}}
    """
    
    for attempt in range(1, 4):
        print(f"\n🤖 AI 전략 진화 시도 ({attempt}/3)...")
        response = client.chat.completions.create(
            model="solar-pro3", 
            messages=[{"role": "user", "content": user_prompt}], 
            temperature=0.2
        )
        new_code = response.choices[0].message.content
        
        # 코드 블록 추출 정교화
        if "```python" in new_code:
            new_code_clean = new_code.split("```python")[1].split("```")[0].strip()
        elif "```" in new_code:
            new_code_clean = new_code.split("```")[1].split("```")[0].strip()
        else:
            new_code_clean = new_code.strip()
        
        # 파일 저장
        with open("src/strategies/strategy_candidate.py", "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        # 문법 및 규격 검증
        is_valid, error_msg = test_code_syntax()
        
        if is_valid: 
            print("✅ 문법 검증 통과! 백테스트를 시작합니다.")
            return new_code_clean
        else: 
            # 에러 발생 시 로그 출력 및 AI에게 피드백 전달
            print(f"❌ 검증 실패 (Attempt {attempt}):\n{error_msg}")
            user_prompt += f"\n\n이전 코드에서 에러가 났어. 아래 에러 메시지를 보고 코드를 수정해줘:\n{error_msg}"
            
    print("🚨 3회 시도 모두 실패했습니다.")
    return None

def run_backtest_and_chart():
    print("📈 백테스트 리포트 생성 중...")
    # indicators.py를 통해 필수 지표 선계산
    df = add_indicators(fetch_historical_data(limit=5000))
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    
    df, d_params = s_cand.apply_strategy(df)
    
    # 컬럼 기반 동적 백테스트 (각 봉의 ATR 기반 TP/SL 적용)
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