import os, sys, traceback, importlib
import pandas as pd
import vectorbt as vbt
from openai import OpenAI
from dotenv import load_dotenv
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

def test_strategy_utility(df):
    """AI가 짠 전략의 기술적 결함을 상세히 보고"""
    try:
        # 캐시 방지를 위해 reload 필수
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        
        res = s_cand.apply_strategy(df.copy())
        
        # 반환 형식 체크
        if not isinstance(res, tuple) or len(res) != 2:
            return False, "반환 형식이 (df, params_dict)가 아닙니다."
            
        df_res, _ = res
        if 'Signal' not in df_res.columns:
            return False, "결과 데이터프레임에 'Signal' 컬럼이 없습니다."
            
        # 신호 발생 여부 체크
        if df_res['Signal'].abs().sum() == 0:
            return False, "최근 데이터에서 매매 신호가 단 한 번도 발생하지 않았습니다. (조건이 너무 까다로움)"
            
        return True, "Success"
    except Exception:
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """전략 생성 시도와 결과(성공여부, 에러내용)를 반환"""
    with open(os.path.join(BASE_DIR, "strategies/strategy.py"), "r", encoding='utf-8') as f:
        current_code = f.read()

    system_prompt = "너는 세계 최고의 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록(```python ... ```)만 출력해."
    user_prompt = f"""
    아래 전략(`strategy.py`)을 더 높은 수익률을 내도록 개선해줘.
    ```python
    {current_code}
    ```
    [필수 규칙]
    1. 'VAL', 'VAH', 'POC', 'CVD', 'ADX', 'Squeeze_On'은 이미 indicators.py에 있으니 절대 다시 계산하지 마.
    2. apply_strategy 함수는 반드시 (df, params_dict) 튜플을 반환해야 해.
    3. vectorbt 사용 시 leverage 인자는 절대 금지.
    """
    
    test_df = add_indicators(fetch_historical_data(limit=1000))
    last_error = "알 수 없는 오류"
    
    for attempt in range(1, 5): # 시도 횟수 상향
        print(f"🤖 AI 전략 진화 시도 중... ({attempt}/4)")
        try:
            resp = client.chat.completions.create(
                model="solar-pro3",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
            )
            raw_content = resp.choices[0].message.content
            
            # 코드 블록 추출 로직 강화
            if "```python" in raw_content:
                new_code = raw_content.split("```python")[1].split("```")[0].strip()
            else:
                new_code = raw_content.strip()

            with open(os.path.join(BASE_DIR, "strategies/strategy_candidate.py"), "w", encoding='utf-8') as f:
                f.write(new_code)
            
            is_valid, msg = test_strategy_utility(test_df)
            if is_valid:
                return True, "Success"
            
            last_error = msg
            user_prompt += f"\n\n[실패 로그]:\n{msg}\n고쳐서 다시 짜줘."
        except Exception as e:
            last_error = str(e)
            
    return False, last_error

def run_backtest_and_chart():
    """검증된 후보 전략 백테스트 실행 및 차트 저장"""
    df = add_indicators(fetch_historical_data(limit=5000))
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df_res, p = s_cand.apply_strategy(df)
    
    # leverage 인자 제거
    pf = vbt.Portfolio.from_signals(
        df_res['close'], 
        entries=(df_res['Signal']==1), 
        short_entries=(df_res['Signal']==-1), 
        tp_stop=p['tp'], 
        sl_stop=p['sl'], 
        freq='3m',
        init_cash=10000
    )
    
    os.makedirs("data/reports", exist_ok=True)
    pf.plot().write_image("data/reports/report.png")
    return pf.total_return() * 100, pf.trades.count()