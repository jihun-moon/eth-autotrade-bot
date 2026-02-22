import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

async def analyze_market_with_ai(df, user_query=None):
    """실시간 지표 기반 AI 정밀 분석"""
    last = df.iloc[-1]
    
    # 지표 데이터 요약
    market_context = {
        "현재가": f"{last['close']:.2f} USDT",
        "RSI": f"{last['RSI']:.2f}",
        "매물대": f"VAL({last['VAL']:.2f}) / POC({last['POC']:.2f}) / VAH({last['VAH']:.2f})",
        "수급(CVD)": f"{'상승 중' if last['CVD'] > last['CVD_Signal'] else '하락 중'}",
        "추세강도(ADX)": f"{last['ADX']:.2f}",
        "변동성(Squeeze)": f"{'응축 중' if last['Squeeze_On'] else '발산 중'}"
    }

    system_msg = "너는 이더리움 퀀트 전문가야. 수치를 바탕으로 포지션 전략과 진입/손절가를 지훈 보스에게 명확히 보고해."
    prompt = f"[시장 데이터]\n{market_context}\n\n[사용자 질문]\n{user_query if user_query else '현재 상황 5줄 이내로 브리핑해줘.'}"

    try:
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            temperature=0.6
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI 분석 오류: {str(e)}"