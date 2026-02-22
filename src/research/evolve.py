import os
import traceback
import importlib
import pandas as pd
import vectorbt as vbt
from openai import OpenAI
from dotenv import load_dotenv
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

load_dotenv()

# Upstage Solar-Pro API 설정
client = OpenAI(
    api_key=os.getenv('UPSTAGE_API_KEY'),
    base_url="https://api.upstage.ai/v1" 
)

def test_code_syntax():
    """AI가 짠 코드가 에러 없이 돌아가는지 가상 테스트 (자가 검증)"""
    try:
        # 지표 계산을 위해 충분한 1000개 데이터 확보
        df = add_indicators(fetch_historical_data(limit=1000))
        
        # 동적 로드 및 리로드
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
            
        res = s_cand.apply_strategy(df)
        
        # 🌟 반환 형식 검증: (df, params_dict)
        if not isinstance(res, tuple) or len(res) != 2:
            return False, "반환 형식이 (df, params_dict)가 아닙니다."
        return True, "Success"
    except Exception:
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """AI를 이용해 코드를 개선하고 에러 발생 시 스스로 수정"""
    strategy_path = "src/strategies/strategy.py"
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    system_prompt = "너는 최고 수준의 가상화폐 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록(```python ... ```)만 출력해."
    
    # 🌟 프롬프트 강화: 정교한 지표(VAL, VAH, CVD) 활용 지시
    user_prompt = f"""
    아래 매매 전략 코드(`strategy.py`)를 개선해줘.
    ```python
    {current_code}
    ```
    [개선 지침]
    1. 데이터프레임에는 이미 'VAL', 'VAH', 'POC', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200' 컬럼이 계산되어 있어.
    2. **핵심 로직**: 가격이 VAL 아래로 이탈했다가 다시 VAL 위로 복귀할 때(Long), VAH 위로 돌파했다가 다시 VAH 아래로 복귀할 때(Short)를 노려.
    3. **수급 필터**: 진입 시 반드시 CVD가 CVD_Signal을 골든크로스/데드크로스 하는 수급 반전을 확인해.
    4. **추세 방어**: ADX가 25 이상이면서 가격이 EMA_200과 멀리 떨어져 있을 때는 역추세 진입을 자제하도록 필터를 짜.
    5. **반환 형식**: 반드시 `return df, params` 형태여야 하며, params에는 'tp'(익절), 'sl'(손절) 비율이 포함되어야 해.
    """
    
    for attempt in range(1, 4):
        print(f"🤖 AI 전략 진화 시도 ({attempt}/3)...")
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.3
        )
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        # 후보 파일 저장
        candidate_path = "src/strategies/strategy_candidate.py"
        with open(candidate_path, "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        is_valid, error_msg = test_code_syntax()
        if is_valid:
            print("✅ AI 코드 문법 및 로직 테스트 통과!")
            return new_code_clean
        else:
            print(f"⚠️ 에러 발생, AI에게 수정을 재요청합니다...")
            user_prompt += f"\n\n[이전 코드 에러 로그]:\n{error_msg}\n위 에러를 해결해서 다시 짜줘."
            
    return None

def run_backtest_and_chart():
    """후보 전략을 10일치 데이터(5000캔들)로 검증하고 차트 생성"""
    print("📊 10일 데이터 백테스트 및 리포트 생성 중...")
    df = add_indicators(fetch_historical_data(limit=5000))
    
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    df, params = s_cand.apply_strategy(df)
    
    # 백테스트 실행
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df.get('Long_Signal', False), 
        short_entries=df.get('Short_Signal', False),
        tp_stop=params.get('tp', 0.02),
        sl_stop=params.get('sl', 0.015), 
        fees=0.0005, 
        freq='3m'
    )
    
    # 리포트 저장 경로 확인
    report_dir = "data/reports"
    os.makedirs(report_dir, exist_ok=True)
    
    # 차트 이미지 저장
    pf.plot().write_image(f"{report_dir}/report.png", width=1200, height=800)
    
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    if generate_and_correct_strategy():
        res_pct, count = run_backtest_and_chart()
        
        # 🌟 보안 강화: 자율 배포 로직 제거
        # 과최적화(Overfitting) 방지를 위해 자동 배포 대신 텔레그램 승인 대기
        print(f"📊 백테스트 결과: 수익률 {res_pct:.2f}%, 거래 횟수 {count}회")
        print("💡 텔레그램에서 /report를 입력하여 차트를 확인하고 실전 반영 여부를 결정하세요.")
        
        # 통계 데이터 저장 (admin_bot이 읽어감)
        with open("data/reports/report_stats.txt", "w") as f:
            f.write(f"{res_pct:.2f},{count}")
        
        print(f"🎉 진화 작업 완료!")