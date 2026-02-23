import ccxt
import os
import logging
import asyncio # 🌟 비동기 처리를 위해 추가
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
    if not exchange: return 1300.0

    try:
        # 선물 계좌의 잔고를 정확히 가져오기 위해 fetch_balance 사용
        balance = exchange.fetch_balance()
        return float(balance['total']['USDT'])
    except Exception as e:
        raise Exception(f"잔고 조회 중 오류 발생: {str(e)}")

async def execute_order(pos_type, amount=None, symbol='ETH/USDT', leverage=10):
    """실전 시장가 주문 및 레버리지 자동 설정"""
    exchange = get_exchange()
    if not exchange:
        logger.info(f"🛒 [테스트] {symbol} {pos_type} 주문 시뮬레이션")
        return True

    try:
        # 1. 🌟 레버리지 자동 설정 (진입 전 필수)
        if pos_type in ['LONG', 'SHORT']:
            await asyncio.to_thread(exchange.set_leverage, leverage, symbol)
        
        # 2. 🌟 비동기 블로킹 방지를 위해 to_thread 사용
        if pos_type == 'LONG':
            await asyncio.to_thread(exchange.create_market_buy_order, symbol, amount)
        elif pos_type == 'SHORT':
            await asyncio.to_thread(exchange.create_market_sell_order, symbol, amount)
        elif pos_type == 'EXIT':
            # 청산 시에는 현재 포지션 수량을 정확히 파악하여 반대 매매
            positions = await asyncio.to_thread(exchange.fetch_positions, [symbol])
            active = next((p for p in positions if float(p['contracts']) != 0), None)
            if active:
                side = 'sell' if float(active['contracts']) > 0 else 'buy'
                await asyncio.to_thread(
                    exchange.create_market_order, 
                    symbol, 'market', side, abs(float(active['contracts'])), 
                    {'reduceOnly': True}
                )
        return True
    except Exception as e:
        raise Exception(f"바이낸스 {symbol} 주문 실패: {str(e)}")