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
    """AI가 생성한 전략의 기술적 결함을 정밀 검증"""
    try:
        # 캐시 방지를 위해 모듈 완전 초기화 후 로드
        if 'strategies.strategy_candidate' in sys.modules:
            del sys.modules['strategies.strategy_candidate']
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        
        # 🌟 전략 실행 테스트 (매개변수 없이 df만 전달)
        res = s_cand.apply_strategy(df.copy())
        
        if not isinstance(res, tuple) or len(res) != 2:
            return False, "반환 형식이 (df, params_dict)가 아닙니다."
            
        df_res, _ = res
        if 'Signal' not in df_res.columns:
            return False, "결과 데이터프레임에 'Signal' 컬럼이 없습니다."
            
        if df_res['Signal'].abs().sum() == 0:
            return False, "최근 데이터에서 매매 신호(1 또는 -1)가 발생하지 않았습니다. (조건이 너무 까다롭거나 논리 오류)"
            
        return True, "Success"
    except Exception:
        # 🌟 발생한 상세 에러 로그(Traceback)를 반환하여 AI 수정을 유도
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """AI에게 엄격한 문법 규칙을 부여하여 전략 생성 및 자가 수정"""
    with open(os.path.join(BASE_DIR, "strategies/strategy.py"), "r", encoding='utf-8') as f:
        current_code = f.read()

    system_prompt = "너는 세계 최고의 파이썬 퀀트 개발자야. 오직 코드 블록(```python ... ```)만 출력해."
    
    # 🌟 프롬프트 대폭 강화: 괄호 규칙 및 지표 중복 금지 명시
    user_prompt = f"""
    아래 전략(`strategy.py`)을 더 높은 수익률을 내도록 개선해줘.
    
    ```python
    {current_code}
    ```
    
    [🚫 절대 준수 규칙 - 위반 시 에러 발생]
    1. **괄호 필수 (Parentheses Rule)**: 여러 조건을 `&`(AND)나 `|`(OR)로 연결할 땐 반드시 각 조건을 괄호로 감싸. 
       - 예: `(df['RSI'] < 30) & (df['CVD'] > 0)` (O) / `df['RSI'] < 30 & df['CVD'] > 0` (X)
    2. **지표 재계산 금지**: 'ADX', 'RSI', 'VAL', 'VAH', 'POC', 'CVD', 'Squeeze_On'은 이미 `indicators.py`에 의해 계산되어 있어. 절대 `ta.adx()`나 `ta.rsi()`를 다시 호출하지 마.
    3. **함수 규격 고정**: 반드시 `def apply_strategy(df):` 형식을 유지하고 결과는 `(df, params_dict)`로 반환해.
    4. **에러 주의**: `ta.adx()`는 데이터프레임을 반환하므로 직접 대입하면 TypeError가 나. 이미 있는 `df['ADX']` 컬럼을 써.
    5. **vectorbt**: leverage 인자는 절대 사용하지 마.
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
            
            if "```python" in raw_content:
                new_code = raw_content.split("```python")[1].split("```")[0].strip()
            else:
                new_code = raw_content.strip()

            with open(os.path.join(BASE_DIR, "strategies/strategy_candidate.py"), "w", encoding='utf-8') as f:
                f.write(new_code)
            
            is_valid, msg = test_strategy_utility(test_df)
            if is_valid:
                return True, "Success"
            
            # 🌟 실패 시 AI에게 독설 섞인 피드백 제공 (특히 bitwise_and 관련)
            last_error = msg
            user_prompt += f"\n\n[❌ 이전 시도 실패 로그]:\n{msg}\n비트 연산자(&, |) 사용 시 각 조건을 괄호()로 감쌌는지, 지표를 다시 계산하지 않았는지 확인해!"
            
        except Exception as e:
            last_error = str(e)
            
    return False, last_error

def run_backtest_and_chart():
    """검증된 후보 전략 백테스트 실행 및 차트 저장"""
    df = add_indicators(fetch_historical_data(limit=5000))
    
    # 최신 전략 모듈 로드
    if 'strategies.strategy_candidate' in sys.modules:
        del sys.modules['strategies.strategy_candidate']
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    
    df_res, p = s_cand.apply_strategy(df)
    
    # 백테스트 실행 (leverage 제거)
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