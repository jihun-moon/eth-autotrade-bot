import os
import traceback
import importlib
import pandas as pd
import vectorbt as vbt
from openai import OpenAI
from dotenv import load_dotenv

# [경로 수정] 새 구조에 맞춘 모듈 임포트
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

load_dotenv()

# Upstage API 세팅
client = OpenAI(
    api_key=os.getenv('UPSTAGE_API_KEY'),
    base_url="https://api.upstage.ai/v1" 
)

def test_code_syntax():
    """AI가 짠 코드가 에러 없이 돌아가는지 가상 테스트"""
    try:
        # 매물대 계산을 위해 최소 480개 이상이 필요하므로 1000개 수집
        df = fetch_historical_data(limit=1000)
        df = add_indicators(df)
        
        # [경로 수정] strategies 폴더 내의 후보 전략 파일을 불러옵니다
        import strategies.strategy_candidate as strategy_candidate
        importlib.reload(strategy_candidate)
        
        # [수정] 반환 형식을 (df, params) 튜플로 받도록 변경 (Unpack 에러 방지)
        df, _ = strategy_candidate.apply_strategy(df)
        return True, "Success"
    except Exception as e:
        return False, traceback.format_exc()

def generate_and_correct_strategy():
    """AI를 이용해 코드를 개선하고 에러 발생 시 스스로 수정"""
    strategy_path = "src/strategies/strategy.py"
    candidate_path = "src/strategies/strategy_candidate.py"
    
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
        
    system_prompt = "너는 최고 수준의 가상화폐 퀀트 트레이더야. 답변은 반드시 파이썬 코드 블록(```python ... ```)만 출력해."
    
    # [수정] AI 지침에 반환 형식(Tuple) 준수 사항 추가
    user_prompt = f"""
    아래는 현재 내 매매 전략 코드야 (`strategy.py`).
    ```python
    {current_code}
    ```
    현재 봇은 횡보장에서는 좋지만 강한 상승/폭락장에서는 스탑로스가 터져.
    내 데이터프레임에는 `df['ADX']` (추세 강도)와 `df['EMA_200']` (장기 추세선) 컬럼이 이미 계산되어 있어.
    
    이 변수들을 조합해서 리스크를 관리하는 새로운 코드를 작성해줘.
    
    [💡 필수 준수 사항]
    1. 파일 맨 위에 반드시 `import pandas_ta as ta` 를 포함해서 전체 완성된 코드를 짜줘.
    2. 강한 추세장(예: ADX > 25)이면서 상승장(close > EMA_200)일 때는 역추세 Short 진입을 차단해.
    3. 강한 추세장이면서 하락장(close < EMA_200)일 때는 역추세 Long 진입을 차단해.
    4. 기존의 VAL, VAH, 다이버전스(Bull_Div, Bear_Div) 로직은 그대로 유지해.
    5. [매우 중요] 함수의 마지막 반환 값은 반드시 `return df, {{'tp': 0.02, 'sl': 0.015}}`와 같이 데이터프레임과 익절/손절 비율 딕셔너리를 포함한 튜플 형태여야 해.
    """
    
    for attempt in range(1, 4):
        print(f"🤖 AI 전략 진화 시도 ({attempt}/3)...")
        
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            stream=False,
            temperature=0.2
        )
        
        new_code = response.choices[0].message.content
        if "```python" in new_code:
            new_code_clean = new_code.split("```python")[1].split("```")[0].strip()
        else:
            new_code_clean = new_code.replace("```", "").strip()
        
        with open(candidate_path, "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        is_valid, error_msg = test_code_syntax()
        if is_valid:
            print("✅ AI 코드 문법 테스트 통과! (에러 없음)")
            return new_code_clean
        else:
            print(f"⚠️ 문법 에러 발생. AI가 스스로 재수정을 시도합니다...\n{error_msg[:200]}")
            user_prompt = f"네가 짜준 코드에 에러가 났어. 고쳐서 다시 전체 코드를 짜줘. 특히 반환 형식이 `return df, params`인지 확인해:\n{error_msg}"
            
    return None

def run_backtest_and_chart():
    """완성된 후보 코드로 백테스트를 돌리고 차트 이미지를 저장"""
    print("📊 5000 캔들 백테스트 및 차트 생성 중...")
    df = fetch_historical_data(limit=5000)
    df = add_indicators(df)
    
    import strategies.strategy_candidate as strategy_candidate
    importlib.reload(strategy_candidate)
    
    # [수정] 반환된 동적 파라미터(d_params)를 백테스트에 적용
    df, d_params = strategy_candidate.apply_strategy(df)
    
    pf = vbt.Portfolio.from_signals(
        df['close'], 
        entries=df.get('Long_Signal', False), 
        short_entries=df.get('Short_Signal', False),
        tp_stop=d_params.get('tp', 0.02),   # AI가 제안한 동적 TP 적용
        sl_stop=d_params.get('sl', 0.015),  # AI가 제안한 동적 SL 적용
        fees=0.0005, 
        slippage=0.001,                    # [추가] 0.1% 슬리피지 반영 (실전 보수적 계산)
        freq='3m'
    )
    
    output_image = "data/reports/report.png"
    fig = pf.plot()
    fig.write_image(output_image, width=1200, height=800)
    
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    os.makedirs("data/reports", exist_ok=True)
    os.makedirs("src/strategies", exist_ok=True)

    if generate_and_correct_strategy():
        return_pct, trade_count = run_backtest_and_chart()
        print(f"🎉 진화 완료! 예상 수익률: {return_pct:.2f}% (거래 횟수: {trade_count})")
        
        stats_file = "data/reports/report_stats.txt"
        with open(stats_file, "w") as f:
            f.write(f"{return_pct:.2f},{trade_count}")