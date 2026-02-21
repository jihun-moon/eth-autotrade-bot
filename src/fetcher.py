import ccxt
import pandas as pd
import os

def fetch_historical_data(symbol='ETH/USDT', timeframe='3m', limit=1000):
    """
    바이낸스에서 특정 코인의 과거 OHLCV 데이터를 가져와 Pandas DataFrame으로 반환합니다.
    (과거 데이터 조회는 API Key가 필요 없습니다.)
    """
    print(f"📡 바이낸스에서 {symbol} {timeframe}봉 데이터를 가져오는 중...")
    
    # 바이낸스 객체 생성
    exchange = ccxt.binance()
    
    # 데이터 요청
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    
    # Pandas 데이터프레임으로 변환 (보기 편한 표 형태로)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # 밀리초 단위 타임스탬프를 한국 시간(KST)으로 변환
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Seoul')
    
    # 시간을 인덱스(기준점)로 설정
    df.set_index('timestamp', inplace=True)
    
    return df

if __name__ == "__main__":
    # 1. data 폴더가 없으면 자동으로 생성
    os.makedirs('data', exist_ok=True)
    
    # 2. 데이터 수집 함수 실행 (이더리움 3분봉 1000개)
    eth_df = fetch_historical_data('ETH/USDT', '3m', 1000)
    
    # 3. 수집한 데이터를 CSV 파일로 저장
    save_path = 'data/eth_3m_historical.csv'
    eth_df.to_csv(save_path)
    
    print(f"✅ 데이터 수집 완료! 총 {len(eth_df)}개의 캔들이 저장되었습니다.")
    print(f"💾 저장 위치: {save_path}")
    
    # 상위 5개 줄만 출력해서 확인
    print("\n[데이터 미리보기]")
    print(eth_df.head())