import os, sys, traceback, importlib
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
        # 캐시 방지를 위해 모듈 초기화 후 로드
        if 'strategies.strategy_candidate' in sys.modules:
            del sys.modules['strategies.strategy_candidate']
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        
        # 전략 실행 테스트
        res = s_cand.apply_strategy(df.copy())
        
        if not isinstance(res, tuple) or len(res) != 2:
            return False, "반환 형식이 (df, params_dict)가 아닙니다."
            
        df_res, _ = res
        if 'Signal' not in df_res.columns:
            return False, "결과 데이터프레임에 'Signal' 컬럼이 없습니다."
            
        if df_res['Signal'].abs().sum() == 0:
            return False, "최근 데이터에서 매매 신호가 발생하지 않았습니다. (조건이 너무 까다로움)"
            
        return True, "Success"
    except Exception:
        # 문법 에러(SyntaxError)를 포함한 상세 로그 반환
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """AI에게 규칙을 강제하며 성공할 때까지 무한히 전략 생성 시도"""
    with open(os.path.join(BASE_DIR, "strategies/strategy.py"), "r", encoding='utf-8') as f:
        current_code = f.read()

    system_prompt = "너는 세계 최고의 파이썬 퀀트 개발자야. 오직 코드 블록(```python ... ```)만 출력해."
    
    # 🌟 할루시네이션 방지를 위한 지표 리스트 및 문법 규칙 강화
    user_prompt = f"""
    아래 전략(`strategy.py`)을 15분봉 스윙 매매에 최적화하여 개선해줘.
    
    ```python
    {current_code}
    ```
    
    [🚫 절대 준수 문법 규칙]
    1. **괄호 필수**: 여러 조건을 `&`(AND)나 `|`(OR)로 연결할 땐 반드시 각 조건을 괄호로 감싸. 
       - 예: `(df['RSI'] < 30) & (df['CVD'] > 0)` (O) / `df['RSI'] < 30 & df['CVD'] > 0` (X)
    2. **지표 재계산 금지**: 아래 지표들은 이미 `indicators.py`에서 계산되어 df에 들어있어. 절대 다시 계산하지 마.
       - 사용 가능 지표: 'RSI', 'EMA_200', 'ADX', 'VAL', 'VAH', 'POC', 'CVD', 'CVD_Signal', 'Squeeze_On'
    3. **함수 규격**: 반드시 `def apply_strategy(df):` 형식을 유지하고 결과는 `(df, params_dict)`로 반환해.
    4. **줄 바꿈**: `&`나 `|`를 줄 끝에 남기지 말고 전체 조건을 괄호 `()`로 묶어 작성해.
    """
    
    # 🌟 15m 데이터로 테스트 수행
    test_df = add_indicators(fetch_historical_data(timeframe='15m', limit=1000))
    attempt = 1
    
    # 🌟 제한 없이(Success 할 때까지) 무한 루프 가동
    while True:
        print(f"🤖 AI 전략 진화 시도 중... (현재 {attempt}회차 시도)")
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
                print(f"✅ {attempt}회차 시도 만에 전략 생성 성공!")
                return True, "Success"
            
            # 에러 발생 시 피드백 루프
            attempt += 1
            user_prompt += f"\n\n[❌ {attempt-1}회차 실패 로그]:\n{msg}\n문법 오류나 지표 참조 에러가 났어. 특히 괄호() 사용과 지표 목록을 확인해서 다시 짜!"
            
        except Exception as e:
            print(f"⚠️ AI 통신 중 오류 발생: {e}")
            attempt += 1

def run_backtest_and_chart():
    """검증된 후보 전략 백테스트 실행 (0.04% 수수료 반영)"""
    # 🌟 15m 타임프레임 및 수수료 설정 반영
    df = add_indicators(fetch_historical_data(timeframe='15m', limit=5000))
    
    if 'strategies.strategy_candidate' in sys.modules:
        del sys.modules['strategies.strategy_candidate']
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    
    df_res, p = s_cand.apply_strategy(df)
    
    # fees=0.0004 (0.04%) 및 freq='15m' 반영
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