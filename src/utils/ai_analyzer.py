import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

async def analyze_market_with_ai(df=None, user_query=None, error_msg=None):
    """15분봉 스윙 매매에 최적화된 AI 분석 핸들러"""
    
    if error_msg:
        system_msg = (
            "너는 지훈 보스의 시스템을 지키는 퀀트 엔지니어 해결사야. "
            "에러 원인을 요약하고, 즉시 취해야 할 행동을 3줄 내외로 명확히 보고해."
        )
        prompt = f"🚨 **시스템 에러 감지**\n내용: {error_msg}\n\n어떻게 해결하면 좋을까?"
    
    else:
        last = df.iloc[-1]
        market_context = {
            "현재가": f"{last['close']:.2f} USDT",
            "RSI": f"{last['RSI']:.2f}",
            "매물대": f"VAL({last['VAL']:.2f}) / POC({last['POC']:.2f}) / VAH({last['VAH']:.2f})",
            "수급(CVD)": "✅ 매수 우위" if last['CVD'] > last['CVD_Signal'] else "❌ 매도 우위",
            "추세강도": f"{last['ADX']:.2f} (ADX)",
            "변동성": "💎 에너지 응축(스퀴즈)" if last['Squeeze_On'] else "🚀 변동성 폭발 중"
        }

        # 🌟 스윙 매매 페르소나 강조
        system_msg = (
            "너는 지훈 보스의 AI 스윙 트레이딩 에이전트 '바텀 스캐너'야.\n"
            "현재 시스템은 15분봉 기반 스윙 매매를 수행 중이므로, 단기 소음보다는 묵직한 추세 대응을 중시해.\n\n"
            "1. 인사와 총평은 한 줄로 엣지 있게 끝낼 것.\n"
            "2. [시장 지표 요약] 섹션은 불렛 포인트(•)를 사용하고 중요 수치는 `코드 블록`으로 감쌀 것.\n"
            "3. [스윙 관점 제안] 섹션에서 LONG, SHORT, WAIT 중 하나를 확실히 정할 것.\n"
            "4. 진입/익절/손절가는 반드시 코드 블록으로 작성해 보스가 복사하기 편하게 할 것:\n"
            "```\n진입: 0000.00\n익절: 0000.00\n손절: 0000.00\n```\n"
            "5. 매물대(VAL/VAH)와 POC를 활용한 지지/저항 돌파 여부에 집중해서 분석해."
        )

        prompt = (
            f"### [15m 스윙 데이터]\n{market_context}\n\n"
            f"### [보스의 질문]\n{user_query if user_query else '현재 상황 스윙 관점에서 분석해줘.'}"
        )

    try:
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            temperature=0.6
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ **AI 에이전트 통신 실패**: {str(e)}"