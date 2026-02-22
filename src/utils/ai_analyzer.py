import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

async def analyze_market_with_ai(df=None, user_query=None, error_msg=None):
    """지표 기반 AI 분석, 일상 대화, 그리고 에러 자가 진단 통합 처리 (모바일 최적화)"""
    
    # 1. 에러 자가 진단 모드 (시스템 에러 발생 시 호출)
    if error_msg:
        system_msg = "너는 퀀트 시스템 엔지니어 해결사야. 발생한 에러를 분석하고 지훈 보스에게 '원인'과 '구체적인 해결 방법'을 3줄 내외로 아주 명확하게 보고해."
        prompt = f"🚨 **시스템 에러 감지**\n내용: {error_msg}\n\n어떻게 해결하면 좋을까?"
    
    # 2. 시장 분석 및 대화 모드
    else:
        last = df.iloc[-1]
        market_context = {
            "현재가": f"{last['close']:.2f} USDT",
            "RSI": f"{last['RSI']:.2f}",
            "매물대": f"VAL({last['VAL']:.2f}) / POC({last['POC']:.2f}) / VAH({last['VAH']:.2f})",
            "수급(CVD)": "✅ 매수 우위" if last['CVD'] > last['CVD_Signal'] else "❌ 매도 우위",
            "추세강도": f"{last['ADX']:.2f} (ADX)",
            "변동성": "💎 응축 중" if last['Squeeze_On'] else "🚀 발산 중"
        }

        # 🤖 텔레그램 가독성을 위한 페르소나 강화
        system_msg = (
            "너는 지훈 보스의 최고의 AI 트레이딩 에이전트 '바텀 스캐너'야.\n"
            "보스가 모바일에서 빠르게 확인할 수 있도록 '핵심 위주'로 답변해.\n"
            "1. 인사는 1줄로 짧고 반갑게 해.\n"
            "2. [지표 요약]은 불렛 포인트(•)를 사용하고, 중요 수치는 `코드 블록`으로 감싸줘.\n"
            "3. [포지션 제안]은 롱/숏/관망 중 하나를 이모지와 함께 확실히 정해줘.\n"
            "4. 진입/익절/손절가는 반드시 아래 형식의 코드 블록으로 작성해서 보스가 바로 복사할 수 있게 해.\n"
            "```\n진입: 0000.00\n익절: 0000.00\n손절: 0000.00\n```\n"
            "5. VAH/VAL 정의 같은 중복 설명은 빼고, 데이터 해석에만 집중해."
        )

        prompt = (
            f"### [실시간 시장 데이터]\n{market_context}\n\n"
            f"### [보스의 메시지]\n{user_query if user_query else '현재 상황 엣지 있게 보고해줘.'}"
        )

    try:
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            temperature=0.6 # 🌟 분석의 일관성을 위해 온도를 살짝 낮춤
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ **AI 에이전트 오류**: {str(e)}"