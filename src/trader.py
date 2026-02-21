import ccxt
import os
from dotenv import load_dotenv

# .env 파일에 숨겨둔 API 키를 불러옵니다.
load_dotenv()

def get_exchange():
    """
    내 API 키가 적용된 안전한 바이낸스 거래소 객체를 생성합니다.
    """
    api_key = os.getenv('BINANCE_API_KEY')
    secret_key = os.getenv('BINANCE_SECRET_KEY')
    
    # 키가 제대로 안 들어왔을 경우 방어
    if not api_key or not secret_key or api_key == "여기에_본인의_API_키를_넣으세요":
        raise ValueError("❌ .env 파일에 바이낸스 API 키가 제대로 설정되지 않았습니다!")

    # ccxt 거래소 셋업
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': secret_key,
        'enableRateLimit': True, # API 호출 제한 방어막 켜기
        'options': {
            'defaultType': 'spot' # 현물 거래 (선물이면 'future'로 변경)
        }
    })
    return exchange

def check_my_balance():
    """
    내 계좌의 현재 USDT(테더) 잔고를 확인합니다.
    """
    print("🔒 바이낸스 거래소에 안전하게 접속 중...")
    exchange = get_exchange()
    
    # 잔고 조회
    balance = exchange.fetch_balance()
    usdt_free = balance['USDT']['free'] # 사용 가능한 USDT 금액
    
    print(f"💰 현재 매매 가능한 USDT 잔고: {usdt_free:.2f} 달러")
    return usdt_free

if __name__ == "__main__":
    print("🚀 매매 실행 엔진(Trader) 테스트 시작!")
    try:
        check_my_balance()
    except Exception as e:
        print(f"\n❌ 거래소 접속 실패: {e}")
        print("💡 해결 방법: .env 파일에 API 키와 Secret 키가 정확히 들어있는지 확인해주세요.")