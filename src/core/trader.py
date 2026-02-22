import ccxt
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("BottomScanner")

def get_exchange():
    """바이낸스 선물 연결 객체 생성"""
    api_key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_SECRET_KEY')
    
    if not api_key or not secret:
        return None

    try:
        return ccxt.binance({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
    except Exception as e:
        logger.error(f"❌ 거래소 연결 실패: {e}")
        return None

def fetch_real_balance():
    """USDT 가용 잔고 조회"""
    exchange = get_exchange()
    if not exchange: return 1300.0 # 테스트 모드 가짜 잔고

    try:
        balance = exchange.fetch_balance()
        return float(balance['total']['USDT'])
    except Exception as e:
        raise Exception(f"잔고 조회 중 오류 발생: {str(e)}")

async def execute_order(pos_type, amount=None, symbol='ETH/USDT'):
    """실전 시장가 주문 및 청산 로직"""
    exchange = get_exchange()
    if not exchange:
        logger.info(f"🛒 [테스트] {symbol} {pos_type} 주문 시뮬레이션")
        return True

    try:
        if pos_type == 'LONG':
            exchange.create_market_buy_order(symbol, amount)
        elif pos_type == 'SHORT':
            exchange.create_market_sell_order(symbol, amount)
        elif pos_type == 'EXIT':
            positions = exchange.fetch_positions([symbol])
            active = next((p for p in positions if float(p['contracts']) != 0), None)
            if active:
                side = 'sell' if float(active['contracts']) > 0 else 'buy'
                exchange.create_market_order(symbol, 'market', side, abs(float(active['contracts'])), {'reduceOnly': True})
        return True
    except Exception as e:
        # 이 에러 메시지가 main.py의 AI 진단으로 전달됩니다.
        raise Exception(f"바이낸스 주문 실패: {str(e)}")