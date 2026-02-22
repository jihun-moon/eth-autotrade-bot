import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
# 업스테이지 Solar API 설정
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

async def analyze_market_with_ai(df=None, user_query=None, error_msg=None):
    """지표 기반 AI 분석, 일상 대화, 에러 자가 진단 통합 핸들러 (모바일 최적화 버전)"""
    
    # 1. 에러 자가 진단 모드: 시스템 장애 시 즉각적인 해결책 보고
    if error_msg:
        system_msg = (
            "너는 지훈 보스의 시스템을 지키는 퀀트 엔지니어 해결사야. "
            "발생한 에러의 원인을 초등학생도 이해하게 요약하고, "
            "보스가 즉시 취해야 할 행동(처방전)을 3줄 내외로 아주 명확하게 보고해."
        )
        prompt = f"🚨 **시스템 에러 감지**\n내용: {error_msg}\n\n어떻게 해결하면 좋을까?"
    
    # 2. 시장 분석 및 전략 제안 모드
    else:
        last = df.iloc[-1]
        # 실시간 핵심 지표 데이터
        market_context = {
            "현재가": f"{last['close']:.2f} USDT",
            "RSI": f"{last['RSI']:.2f}",
            "매물대": f"VAL({last['VAL']:.2f}) / POC({last['POC']:.2f}) / VAH({last['VAH']:.2f})",
            "수급(CVD)": "✅ 매수 우위" if last['CVD'] > last['CVD_Signal'] else "❌ 매도 우위",
            "추세강도": f"{last['ADX']:.2f} (ADX)",
            "변동성": "💎 에너지 응축(스퀴즈)" if last['Squeeze_On'] else "🚀 변동성 폭발 중"
        }

        # 🤖 지능형 페르소나 및 모바일 가독성 설정
        system_msg = (
            "너는 지훈 보스의 1호 AI 트레이딩 에이전트 '바텀 스캐너'야.\n"
            "보스가 밖에서 폰으로 봐도 3초 만에 판단이 서도록 '압축 보고'하는 것이 너의 사명이다.\n\n"
            "1. 인사와 총평은 한 줄로 엣지 있게 끝낼 것. (예: 보스, 지금 하락 압력이 심상치 않네요!)\n"
            "2. [시장 지표 요약] 섹션은 불렛 포인트(•)를 사용하고, 중요 수치는 `코드 블록`으로 감싸줄 것.\n"
            "3. [포지션 제안]은 🔴 SHORT, 🟢 LONG, ⚪️ WAIT 중 하나를 확실히 정할 것.\n"
            "4. 진입/익절/손절가는 반드시 아래 형식의 코드 블록으로 작성해 보스가 꾹 눌러 복사할 수 있게 해줄 것:\n"
            "```\n진입: 0000.00\n익절: 0000.00\n손절: 0000.00\n```\n"
            "5. VAL/VAH 정의 같은 지식 자랑은 절대 하지 마. 오직 '데이터 해석'과 '결론'에만 집중해."
        )

        prompt = (
            f"### [실시간 시장 데이터]\n{market_context}\n\n"
            f"### [보스의 질문]\n{user_query if user_query else '현재 상황 엣지 있게 분석해줘.'}"
        )

    try:
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            temperature=0.6 # 일관성 있는 분석을 위해 온도를 살짝 낮게 유지
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ **AI 에이전트 통신 실패**: {str(e)}"