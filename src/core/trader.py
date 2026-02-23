import ccxt
import os
import logging
import asyncio
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("BottomScanner")

def get_exchange():
    """바이낸스 선물 연결 객체 생성 (타임아웃 및 예외 처리 강화)"""
    api_key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_SECRET_KEY')
    
    # 🌟 테스트 모드: API 키가 없으면 바로 None 반환하여 시뮬레이션 유도
    if not api_key or not secret:
        return None

    try:
        return ccxt.binance({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'timeout': 30000, # 🌟 연결 대기 시간을 30초로 늘려 네트워크 에러 방지
            'options': {'defaultType': 'future'}
        })
    except Exception as e:
        logger.warning(f"⚠️ 거래소 연결 시도 중 에러 (시뮬레이션 모드 전환): {e}")
        return None

def fetch_real_balance():
    """잔고 조회 (에러 발생 시 테스트용 잔고 1300.0 반환)"""
    exchange = get_exchange()
    
    # 🌟 거래소 객체가 없으면 시뮬레이션 잔고 반환
    if not exchange: 
        return 1300.0 

    try:
        # 🌟 네트워크 에러 등으로 실패할 경우를 대비해 비동기 안전장치 고려 가능
        balance = exchange.fetch_balance()
        return float(balance['total']['USDT'])
    except Exception as e:
        # 🌟 중요: 실전 매매가 아닌 '테스트' 중이므로 에러 시 봇을 멈추지 않고 가짜 잔고 반환
        logger.error(f"⚠️ 실전 잔고 조회 실패 (테스트 잔고 사용): {e}")
        return 1300.0 

async def execute_order(pos_type, amount=None, symbol='ETH/USDT', leverage=10):
    """주문 집행 (연결 실패 시 로그만 남기고 성공으로 간주하여 시뮬레이션 유지)"""
    exchange = get_exchange()
    
    # 🌟 시뮬레이션 로그 출력
    if not exchange:
        logger.info(f"🧪 [시뮬레이션] {symbol} {pos_type} {amount} 주문 실행 완료")
        return True

    try:
        # 레버리지 설정
        if pos_type in ['LONG', 'SHORT']:
            await asyncio.to_thread(exchange.set_leverage, leverage, symbol)
        
        # 주문 실행
        if pos_type == 'LONG':
            await asyncio.to_thread(exchange.create_market_buy_order, symbol, amount)
        elif pos_type == 'SHORT':
            await asyncio.to_thread(exchange.create_market_sell_order, symbol, amount)
        elif pos_type == 'EXIT':
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
        # 🌟 테스트 중에는 주문 실패가 봇 전체의 종료로 이어지지 않게 처리 가능
        # 실전 전환 시에는 이 부분을 다시 raise Exception으로 바꿔야 안전합니다.
        logger.error(f"❌ 바이낸스 주문 실패: {e}")
        return False # 🌟 테스트 중에는 에러가 나도 False만 반환하여 루프 유지