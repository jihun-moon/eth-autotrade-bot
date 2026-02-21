import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

def get_exchange():
    """
    거래소 연결 객체 생성 (현재 API 미연결로 주석 처리)
    나중에 자동매매를 시작할 때 아래 주석(#)을 해제하세요.
    """
    # api_key = os.getenv('BINANCE_API_KEY')
    # secret_key = os.getenv('BINANCE_SECRET_KEY')
    # 
    # if not api_key or not secret_key or api_key == "여기에_본인의_API_키를_넣으세요":
    #     raise ValueError("❌ .env 파일에 바이낸스 API 키가 제대로 설정되지 않았습니다!")
    #
    # exchange = ccxt.binance({
    #     'apiKey': api_key,
    #     'secret': secret_key,
    #     'enableRateLimit': True,
    #     'options': {
    #         'defaultType': 'spot' 
    #     }
    # })
    # return exchange
    pass

def check_my_balance():
    """내 계좌 잔고 확인 (테스트를 위해 가짜 잔고 반환)"""
    print("🔒 [테스트 모드] 실제 거래소 잔고 조회를 건너뜁니다.")
    
    # 실제 잔고 조회 코드 (주석 처리됨)
    # exchange = get_exchange()
    # balance = exchange.fetch_balance()
    # usdt_free = balance['USDT']['free']
    # return usdt_free
    
    return 1000.0  # 가상의 1000 USDT 잔고 반환

def execute_buy_order(symbol='ETH/USDT', usdt_amount=None):
    """실제 매수 주문 실행 (현재는 알림만 띄우고 넘김)"""
    print(f"🛒 [테스트 모드] {symbol} 매수 로직 도달! (실제 매수는 진행되지 않습니다)")
    
    # 실제 매수 주문 코드 (주석 처리됨)
    # exchange = get_exchange()
    # try:
    #     if usdt_amount is None:
    #         usdt_amount = check_my_balance() * 0.95 
    #     if usdt_amount < 5: 
    #         return None
    #
    #     ticker = exchange.fetch_ticker(symbol)
    #     current_price = ticker['last']
    #     amount_to_buy = usdt_amount / current_price
    #     
    #     order = exchange.create_market_buy_order(symbol, amount_to_buy)
    #     print(f"✅ 매수 체결 완료! (체결가: {current_price}, 수량: {amount_to_buy})")
    #     return order
    # except Exception as e:
    #     print(f"❌ 매수 주문 중 에러 발생: {e}")
    #     return None

    return {"status": "test_mode"} # 에러 방지용 가짜 결과 반환