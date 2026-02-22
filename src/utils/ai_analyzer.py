import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv('UPSTAGE_API_KEY'), base_url="https://api.upstage.ai/v1")

async def analyze_market_with_ai(df=None, user_query=None, error_msg=None):
    """지표 기반 AI 분석, 일상 대화, 그리고 에러 자가 진단 통합 처리"""
    
    # 1. 에러 자가 진단 모드 (시스템 에러 발생 시 호출)
    if error_msg:
        system_msg = "너는 퀀트 시스템 엔지니어이자 해결사야. 발생한 에러를 분석하고 지훈 보스에게 '원인'과 '구체적인 해결 방법'을 3줄 내외로 보고해."
        prompt = f"🚨 **시스템 에러 감지**\n내용: {error_msg}\n\n어떻게 해결하면 좋을까?"
    
    # 2. 시장 분석 및 대화 모드
    else:
        last = df.iloc[-1]
        market_context = {
            "현재가": f"{last['close']:.2f} USDT",
            "RSI": f"{last['RSI']:.2f}",
            "매물대": f"하단 VAL({last['VAL']:.2f}) / 중앙 POC({last['POC']:.2f}) / 상단 VAH({last['VAH']:.2f})",
            "수급(CVD)": f"{'✅ 매수 우위' if last['CVD'] > last['CVD_Signal'] else '❌ 매도 우위'}",
            "추세강도": f"{last['ADX']:.2f} (ADX)",
            "변동성": f"{'💎 에너지 응축 중(스퀴즈)' if last['Squeeze_On'] else '🚀 추세 폭발 중'}"
        }

        system_msg = (
            "너는 지훈 보스의 최고의 AI 트레이딩 에이전트 '바텀 스캐너'야.\n"
            "1. 사용자가 '안녕', '반가워' 등 인사를 하면 차트 분석보다 먼저 반갑게 인사를 건네고 대화를 시작해.\n"
            "2. 분석 요청 시에는 반드시 제공된 [시장 데이터]를 근거로 논리적인 포지션(롱/숏/관망)을 추천해.\n"
            "3. 익절/손절가는 매물대 수치를 참고해서 구체적으로 제시해.\n"
            "4. 답변은 텔레그램 마크다운 스타일을 활용하고 이모지를 섞어 예쁘게 작성해."
        )

        prompt = (
            f"### [실시간 시장 데이터]\n{market_context}\n\n"
            f"### [보스의 메시지]\n{user_query if user_query else '현재 상황 5줄 내외로 요약 보고해줘.'}"
        )

    try:
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ **AI 에이전트 오류**: {str(e)}"