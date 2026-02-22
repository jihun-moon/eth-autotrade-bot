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

async def execute_order(pos_type, amount=None, symbol='ETH/USDT'):
    """
    시장가 주문 실행 로직.
    pos_type: 'LONG', 'SHORT', 'EXIT' (포지션 종료)
    """
    exchange = get_exchange()
    
    # 테스트 모드 처리
    if exchange is None:
        logger.info(f"🛒 [테스트 모드] {symbol} {pos_type} 주문 시뮬레이션")
        return {"id": "test_order_id", "status": "closed", "price": "market"}

    try:
        order = None
        
        # 1. LONG 진입 (매수)
        if pos_type == 'LONG':
            order = exchange.create_market_buy_order(symbol, amount)
            logger.info(f"✅ [실전 체결] LONG 진입 성공! (수량: {amount})")
            
        # 2. SHORT 진입 (매도)
        elif pos_type == 'SHORT':
            order = exchange.create_market_sell_order(symbol, amount)
            logger.info(f"✅ [실전 체결] SHORT 진입 성공! (수량: {amount})")
            
        # 3. EXIT (포지션 청산) - 현재 포지션을 확인하여 반대 방향으로 주문
        elif pos_type == 'EXIT':
            # 현재 해당 심볼의 포지션 정보 가져오기
            positions = exchange.fetch_positions([symbol])
            # 수량이 0이 아닌 활성화된 포지션 찾기
            active_position = next((p for p in positions if float(p['contracts']) != 0), None)
            
            if active_position:
                size = float(active_position['contracts'])
                # 현재 포지션이 Long(양수)이면 Sell, Short(음수)이면 Buy 주문
                side = 'sell' if size > 0 else 'buy'
                
                # reduceOnly 설정을 통해 신규 포지션이 잡히지 않고 기존 포지션만 종료되도록 보장
                order = exchange.create_market_order(
                    symbol=symbol,
                    type='market',
                    side=side,
                    amount=abs(size),
                    params={'reduceOnly': True}
                )
                logger.info(f"✅ [실전 체결] {pos_type} 청산 성공! (방향: {side}, 수량: {abs(size)})")
            else:
                logger.warning(f"⚠️ {symbol}에 종료할 활성화된 포지션이 없습니다.")
                return None

        return order

    except Exception as e:
        logger.error(f"❌ 주문 실행 중 치명적 에러: {e}")
        return None