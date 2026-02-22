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
    3. 실제 거래 신호(Signal) 발생 여부
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
            return False, "생성된 전략에서 거래 신호가 0회 발생했습니다. 필터를 완화해서 다시 짜주세요."
            
        return True, "Success"
    except Exception:
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """AI를 이용해 코드를 개선하고, 결과가 부적합하면 처음부터 다시 짜게 함"""
    strategy_path = os.path.join(BASE_DIR, "strategies/strategy.py")
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    system_prompt = "너는 최고 수준의 가상화폐 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록(```python ... ```)만 출력해."
    
    # 🌟 AI의 기술적 실수를 방지하기 위한 정교한 프롬프트 (수정됨)
    user_prompt = f"""
    아래 매매 전략 코드(`strategy.py`)를 개선해줘.
    ```python
    {current_code}
    ```
    [반드시 지켜야 할 파이썬 문법 규칙]
    1. **불리언 마스크 안전화**: `~` 연산자를 쓰기 전에 반드시 `.astype(bool)`을 적용해. (예: `(~df['col'].astype(bool))`)
    2. **np.where 결과 처리**: `np.where()` 결과에 바로 `.ffill()`을 쓸 수 없어. 반드시 Series로 변환해. 
       (예: `df['Price'] = pd.Series(np.where(cond, val, np.nan), index=df.index).ffill()`)
    3. **이전 값 참조**: `df['VAL'].shift(1)`처럼 직접 `.shift()`를 사용해 비교해.
    4. **모호한 진실값 방지**: Series 전체를 직접적인 `== True`로 비교하지 마. 반드시 비트 연산자(`&`, `|`)를 사용해.
    5. **기존 데이터 활용**: 'VAL', 'VAH', 'CVD', 'ADX', 'EMA_200'은 이미 존재하므로 `ta.` 함수로 다시 계산하지 마.

    [개선 로직]
    - Long: 가격이 VAL 아래에 있다가(1개 전 캔들) 현재 VAL 위로 복귀하며 CVD가 상승할 때.
    - Short: 가격이 VAH 위에 있다가(1개 전 캔들) 현재 VAH 아래로 복귀하며 CVD가 하락할 때.
    - 거래 빈도가 너무 낮지 않게 조건을 유연하게 가져가줘.
    """
    
    # 지표가 포함된 테스트용 데이터 준비
    test_df = add_indicators(fetch_historical_data(limit=1000))
    candidate_path = os.path.join(BASE_DIR, "strategies/strategy_candidate.py")
    
    for attempt in range(1, 6): # 시도 횟수 확보
        print(f"🤖 AI 전략 유연 진화 시도 ({attempt}/5)...")
        
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.4 
        )
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        # 파일 저장
        with open(candidate_path, "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        # 실효성 테스트 실행
        is_valid, error_msg = test_strategy_utility(test_df)
        if is_valid:
            print("✅ 전략 유효성 검사 통과! (거래 신호 확인됨)")
            return new_code_clean
        else:
            print(f"⚠️ 전략 보완 필요: {error_msg}")
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

    # 🌟 오픈소스 버전 vectorbt 호환성을 위해 leverage 인자 제거
    # 실제 레버리지는 main.py에서 수량 조절로 처리됩니다.
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
    
    # 경로 수정: BASE_DIR 외부의 data/reports 폴더로 지정
    report_dir = os.path.join(os.path.dirname(BASE_DIR), "data/reports")
    os.makedirs(report_dir, exist_ok=True)
    pf.plot().write_image(os.path.join(report_dir, "report.png"), width=1200, height=800)
    
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res_pct, count = run_backtest_and_chart()
        
        print(f"📊 백테스트 결과: 수익률 {res_pct:.2f}%, 거래 횟수 {count}회")
        
        # 통계 데이터 저장 경로 수정
        report_dir = os.path.join(os.path.dirname(BASE_DIR), "data/reports")
        stats_file = os.path.join(report_dir, "report_stats.txt")
        with open(stats_file, "w") as f:
            f.write(f"{res_pct:.2f},{count}")
        
        print(f"🎉 진화 작업 완료!")