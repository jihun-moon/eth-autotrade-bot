import ccxt
import os
import logging
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 구조화된 로깅 설정
logger = logging.getLogger("BottomScanner")

def get_exchange():
    """
    바이낸스 거래소 연결 객체 생성.
    API 키가 없거나 기본값이면 None을 반환하여 테스트 모드로 유도합니다.
    """
    api_key = os.getenv('BINANCE_API_KEY')
    secret_key = os.getenv('BINANCE_SECRET_KEY')
    
    # API 키 유효성 검사
    if not api_key or not secret_key or api_key == "여기에_본인의_API_키를_넣으세요":
        return None

    try:
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'  # 선물 매매(양방향)를 위해 future 설정
            }
        })
        return exchange
    except Exception as e:
        logger.error(f"❌ 거래소 객체 생성 중 에러: {e}")
        return None

def fetch_real_balance():
    """실제 USDT 잔고 조회 (키가 없으면 테스트용 가짜 잔고 반환)"""
    exchange = get_exchange()
    
    if exchange is None:
        logger.info("🔒 [테스트 모드] 가상 잔고 1300.0 USDT 사용")
        return 1300.0
    
    try:
        balance = exchange.fetch_balance()
        # 선물 계정의 총 USDT 잔고 반환
        usdt_balance = float(balance['total']['USDT'])
        return usdt_balance
    except Exception as e:
        logger.error(f"❌ 잔고 조회 실패: {e}")
        return 0.0

async def execute_order(pos_type, amount, symbol='ETH/USDT'):
    """
    시장가 주문 실행 로직.
    pos_type: 'LONG', 'SHORT', 'EXIT' (포지션 종료)
    """
    exchange = get_exchange()
    current_price = 0.0 # 로그용
    
    if exchange is None:
        logger.info(f"🛒 [테스트 모드] {symbol} {pos_type} 주문 시뮬레이션 (수량: {amount:.4f})")
        return {"id": "test_order_id", "status": "closed", "price": "market"}

    try:
        # 1. 현재 가격 조회 (로그용)
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        
        order = None
        # 2. 포지션 방향에 따른 시장가 주문 실행
        if pos_type == 'LONG':
            # 매수(Open Long)
            order = exchange.create_market_buy_order(symbol, amount)
        elif pos_type == 'SHORT':
            # 매도(Open Short)
            order = exchange.create_market_sell_order(symbol, amount)
        elif pos_type == 'EXIT':
            # 반대 매매를 통한 포지션 종료 (상세 로직은 포지션 정보 확인 후 처리 권장)
            # 여기서는 단순 시장가 청산 예시
            # order = exchange.create_market_order(symbol, 'sell' if 현재가LONG else 'buy', amount)
            logger.warning("⚠️ EXIT 주문은 현재 계정의 포지션 방향 확인 로직이 추가로 필요합니다.")
            pass

        if order:
            logger.info(f"✅ [실전 체결] {pos_type} 성공! (ID: {order['id']}, 가격: {current_price})")
            return order

    except Exception as e:
        logger.error(f"❌ 주문 실행 중 치명적 에러: {e}")
        return None

    return None