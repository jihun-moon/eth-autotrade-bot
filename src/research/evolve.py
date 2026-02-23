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
    """AI 전략의 문법 및 실행 유효성 검증"""
    try:
        if 'strategies.strategy_candidate' in sys.modules:
            del sys.modules['strategies.strategy_candidate']
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        
        res = s_cand.apply_strategy(df.copy())
        
        if not isinstance(res, tuple) or len(res) != 2:
            return False, "반환 형식이 (df, params_dict)가 아닙니다."
            
        df_res, _ = res
        if 'Signal' not in df_res.columns:
            return False, "결과 데이터프레임에 'Signal' 컬럼이 없습니다."
            
        if df_res['Signal'].abs().sum() == 0:
            return False, "최근 데이터에서 매매 신호가 발생하지 않았습니다. (조건이 너무 까다롭거나 논리 오류)"
            
        return True, "Success"
    except Exception:
        # 🌟 문법 에러(SyntaxError)를 포함한 상세 로그 반환
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """AI에게 문법 및 지표 규칙을 강제하여 전략 생성"""
    with open(os.path.join(BASE_DIR, "strategies/strategy.py"), "r", encoding='utf-8') as f:
        current_code = f.read()

    system_prompt = "너는 세계 최고의 퀀트 개발자야. 오직 코드 블록(```python ... ```)만 출력해."
    
    # 🌟 프롬프트 강화: 줄 바꿈 규칙 및 지표 제한 추가
    user_prompt = f"""
    아래 전략(`strategy.py`)을 더 높은 수익률을 내도록 개선해줘.
    
    ```python
    {current_code}
    ```
    
    [🚫 절대 준수 문법 규칙]
    1. **줄 바꿈 금지**: `&`나 `|` 같은 연산자를 줄 끝에 남기지 마. 여러 줄을 쓸 거면 전체 조건을 괄호 `(...)`로 감싸.
    2. **지표 제한**: 오직 'RSI', 'EMA_200', 'ADX', 'VAL', 'VAH', 'POC', 'CVD', 'Squeeze_On'만 사용해. `EMA50`이나 `MACD` 같은 없는 지표를 지어내지 마.
    3. **함수 규격**: 반드시 `def apply_strategy(df):` 형식을 유지하고 결과는 `(df, params_dict)`로 반환해.
    4. **지표 재계산 금지**: `ta.adx()` 등을 코드 내에서 다시 호출하지 마. 이미 있는 컬럼을 그대로 써.
    """
    
    test_df = add_indicators(fetch_historical_data(limit=1000))
    last_error = "알 수 없는 오류"
    
    for attempt in range(1, 5):
        print(f"🤖 AI 전략 진화 시도 중... ({attempt}/4)")
        try:
            resp = client.chat.completions.create(
                model="solar-pro3",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
            )
            raw_content = resp.choices[0].message.content
            
            new_code = raw_content.split("```python")[1].split("```")[0].strip() if "```python" in raw_content else raw_content.strip()

            with open(os.path.join(BASE_DIR, "strategies/strategy_candidate.py"), "w", encoding='utf-8') as f:
                f.write(new_code)
            
            is_valid, msg = test_strategy_utility(test_df)
            if is_valid:
                return True, "Success"
            
            # 🌟 에러 발생 시 AI에게 구체적으로 꾸짖음
            last_error = msg
            user_prompt += f"\n\n[❌ 실행 에러 발생]:\n{msg}\n문법 오류가 났어! 특히 줄 끝에 '&'를 남겼거나 없는 지표를 썼는지 확인해서 다시 짜!"
            
        except Exception as e:
            last_error = str(e)
            
    return False, last_error

def run_backtest_and_chart():
    """검증된 후보 전략 백테스트 실행 (0.04% 수수료 반영)"""
    # 🌟 15m 타임프레임으로 데이터 수집
    df = add_indicators(fetch_historical_data(timeframe='15m', limit=5000))
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df_res, p = s_cand.apply_strategy(df)
    
    # 🌟 fees=0.0004 (0.04%) 및 freq='15m' 반영
    pf = vbt.Portfolio.from_signals(
        df_res['close'], 
        entries=(df_res['Signal']==1), 
        short_entries=(df_res['Signal']==-1), 
        tp_stop=p['tp'], 
        sl_stop=p['sl'], 
        freq='15m', 
        init_cash=10000,
        fees=0.0004 
    )
    
    os.makedirs("data/reports", exist_ok=True)
    pf.plot().write_image("data/reports/report.png")
    return pf.total_return() * 100, pf.trades.count()