import os
import traceback
import importlib
import pandas as pd
import vectorbt as vbt
import numpy as np
import logging
from openai import OpenAI
from dotenv import load_dotenv
from utils.fetcher import fetch_historical_data
from utils.indicators import add_indicators

# 로깅 설정: 소음 최소화
logging.basicConfig(level=logging.ERROR)
load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

def fetch_market_context():
    """AI가 판단에 참고할 외부 데이터 (청산맵, 심리 지표 등)"""
    return {
        "liquidation_clusters": "1940$ (Long Liquidation Heavy), 1995$ (Short Liquidation Heavy)",
        "funding_rate": "0.01% (Normal)",
        "sentiment": "Neutral (Fear & Greed Index: 45)"
    }

def test_code_syntax():
    """생성된 코드의 규격 검증 (KeyError 및 AttributeError 방지)"""
    try:
        df = add_indicators(fetch_historical_data(limit=1000))
        import strategies.strategy_candidate as s_cand
        importlib.reload(s_cand)
        # 기본 인자로 실행 테스트
        res = s_cand.apply_strategy(df)
        if not isinstance(res, tuple) or len(res) != 2:
            raise ValueError("반환 형식이 반드시 (df, params_dict) 튜플이어야 합니다.")
        return True, "Success"
    except Exception:
        return False, traceback.format_exc()

def find_best_params(df_ind):
    """한 달 치 데이터 내에서 최고의 수익률을 내는 수치 조합을 강제로 탐색"""
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    
    ema_list = [20, 30, 50]
    tp_mults = [1.5, 2.0, 2.5, 3.0]
    sl_mults = [1.0, 1.5, 2.0]
    
    best_ret = -np.inf
    best_params = {'ema': 30, 'tp_mult': 2.0, 'sl_mult': 1.5}
    
    print("🔎 한 달(15,000캔들) 데이터 기반 최적 수치 조합 탐색 중...")
    
    for ema in ema_list:
        try:
            # 전략 로직 적용 (EMA 변경)
            df_temp, _ = s_cand.apply_strategy(df_ind.copy(), ema_len=ema)
            for tp in tp_mults:
                for sl in sl_mults:
                    # 동적 TP/SL 컬럼 재산출
                    t_tp = (df_temp['ATR'] * tp / df_temp['close']).fillna(0.02)
                    t_sl = (df_temp['ATR'] * sl / df_temp['close']).fillna(0.015)
                    
                    pf = vbt.Portfolio.from_signals(
                        df_temp['close'],
                        entries=df_temp.get('Long_Signal', False),
                        short_entries=df_temp.get('Short_Signal', False),
                        tp_stop=t_tp, sl_stop=t_sl, fees=0.0005, freq='3m'
                    )
                    
                    total_ret = pf.total_return()
                    if total_ret > best_ret:
                        best_ret = total_ret
                        best_params = {'ema': ema, 'tp_mult': tp, 'sl_mult': sl}
        except: continue
    
    print(f"🏆 최적 수치 발견: EMA {best_params['ema']}, TP {best_params['tp_mult']}배, SL {best_params['sl_mult']}배 (Return: {best_ret*100:.2f}%)")
    return best_params

def generate_and_correct_strategy(prev_stats=None):
    strategy_path = "src/strategies/strategy.py"
    with open(strategy_path, "r", encoding="utf-8") as f:
        current_code = f.read()
    
    m_data = fetch_market_context()
    feedback = f"이전 수익률: {prev_stats['return']}%" if prev_stats else "첫 시도입니다."

    # [수정] AI 환각을 방어하는 극도로 강력한 프롬프트
    user_prompt = f"""
    [현재 상황] {feedback}
    [시장 데이터] 청산 밀집: {m_data['liquidation_clusters']}, 펀딩비: {m_data['funding_rate']}

    위 정보를 참고하여 아래 매매 전략 코드를 개선해줘.
    ```python
    {current_code}
    ```

    [🚨 슈퍼 준수 사항 - 위반 시 즉시 에러]
    1. **중복 지표 계산 금지**: 이미 `df`에는 'ADX', 'CVD', 'CVD_Signal', 'EMA_200', 'VAL', 'VAH', 'RSI' 컬럼이 있어.
       - 절대로 `ta.adx()`, `ta.vp()`, `df.adx()` 같은 함수를 호출하지 마!
       - 그냥 `df['ADX']`, `df['VAL']` 처럼 기존 컬럼을 사용해.
    2. **ATR 필수**: `df['ATR']`은 반드시 `ta.atr(df['high'], df['low'], df['close'], length=14)`로 직접 계산해.
    3. **동적 TP/SL**: 반드시 `target_tp`와 `target_sl` 컬럼을 ATR과 인자(`tp_mult`, `sl_mult`)를 사용해 생성해.
    4. **청산맵 활용**: 청산 물량이 많은 가격대({m_data['liquidation_clusters']}) 근처에서 가격이 반전되는 'Liquidity Sweep' 로직을 추가해봐.
    5. **함수 인자**: `apply_strategy(df, ema_len=30, tp_mult=2.0, sl_mult=1.5)` 형태를 유지해.
    6. **반환 규격**: `return df, {{'tp': last_tp, 'sl': last_sl}}` 형태를 유지해.
    """
    
    for attempt in range(1, 4):
        print(f"\n🤖 AI 전략 진화 시도 ({attempt}/3)...")
        response = client.chat.completions.create(model="solar-pro3", messages=[{"role": "user", "content": user_prompt}], temperature=0.2)
        new_code = response.choices[0].message.content
        new_code_clean = new_code.split("```python")[1].split("```")[0].strip() if "```python" in new_code else new_code.strip()
        
        with open("src/strategies/strategy_candidate.py", "w", encoding="utf-8") as f:
            f.write(new_code_clean)
            
        is_valid, error_msg = test_code_syntax()
        if is_valid: return new_code_clean
        else: 
            print(f"❌ 검증 실패: {error_msg}")
            user_prompt += f"\n\n오류 발생! 아래 에러를 해결해: {error_msg}"
    return None

def run_backtest_and_chart():
    # 🌟 한 달(15,000캔들) 데이터 수집
    print("📥 한 달 분량 데이터 수집 중...")
    df = add_indicators(fetch_historical_data(limit=15000))
    
    # 최고의 수치 조합 탐색
    best = find_best_params(df.copy())
    
    import strategies.strategy_candidate as s_cand
    importlib.reload(s_cand)
    
    try:
        # 최적화된 수치로 최종 결과 도출
        df, _ = s_cand.apply_strategy(df, ema_len=best['ema'], tp_mult=best['tp_mult'], sl_mult=best['sl_mult'])
    except:
        df, _ = s_cand.apply_strategy(df)

    pf = vbt.Portfolio.from_signals(
        df['close'], entries=df.get('Long_Signal', False), short_entries=df.get('Short_Signal', False),
        tp_stop=df['target_tp'], sl_stop=df['target_sl'], fees=0.0005, slippage=0.001, freq='3m'
    )
    
    os.makedirs("data/reports", exist_ok=True)
    pf.plot().write_image("data/reports/report.png", width=1200, height=800)
    return pf.total_return() * 100, pf.trades.count()

if __name__ == "__main__":
    prev_info = None
    if os.path.exists("data/reports/report_stats.txt"):
        with open("data/reports/report_stats.txt", "r") as f:
            s = f.read().split(',')
            if len(s) == 2: prev_info = {'return': s[0], 'count': s[1]}

    if generate_and_correct_strategy(prev_info):
        res_pct, count = run_backtest_and_chart()
        with open("data/reports/report_stats.txt", "w") as f: f.write(f"{res_pct:.2f},{count}")