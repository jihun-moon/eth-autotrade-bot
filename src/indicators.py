import pandas as pd
import pandas_ta as ta
import numpy as np
import os

def add_indicators(df):
    """
    OHLCV 데이터프레임에 전략에 필요한 기술적 지표를 가장 안전한 방식으로 추가합니다.
    """
    print("⚙️ 기술적 지표(RSI, EMA, Squeeze, CVD) 계산 중...")
    print(f"  👉 초기 캔들 개수: {len(df)}개")
    
    # 1. 숫자형 데이터로 안전하게 덮어쓰기
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    # 2. 기본 지표 추가
    df.ta.rsi(length=14, append=True)
    df.ta.ema(length=50, append=True)
    
    # 3. 스퀴즈 모멘텀
    df.ta.bbands(length=20, std=2.0, append=True)
    df.ta.kc(length=20, scalar=1.5, append=True)
    
    try:
        bbl_col = [c for c in df.columns if c.startswith('BBL')][0]
        bbu_col = [c for c in df.columns if c.startswith('BBU')][0]
        kcl_col = [c for c in df.columns if c.startswith('KCL')][0]
        kcu_col = [c for c in df.columns if c.startswith('KCU')][0]
        df['Squeeze_On'] = (df[bbl_col] > df[kcl_col]) & (df[bbu_col] < df[kcu_col])
    except Exception as e:
        df['Squeeze_On'] = False

    # 4. 세력 확인 필터 (CVD) - 배열 인덱스 꼬임 완벽 방지
    spread = df['high'] - df['low']
    spread = spread.replace(0, 0.00001) # numpy 대신 pandas 고유 함수 사용
    
    upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
    lower_wick = df[['open', 'close']].min(axis=1) - df['low']
    body_length = (df['open'] - df['close']).abs()
    
    pct_upper = upper_wick / spread
    pct_lower = lower_wick / spread
    pct_body = body_length / spread
    wick_avg = (pct_upper + pct_lower) / 2
    
    is_bull = df['close'] > df['open']
    is_bear = df['close'] < df['open']
    
    buying_vol = np.where(is_bull, (pct_body + wick_avg) * df['volume'], wick_avg * df['volume'])
    selling_vol = np.where(is_bear, (pct_body + wick_avg) * df['volume'], wick_avg * df['volume'])
    
    delta = buying_vol - selling_vol
    # Series 인덱스를 명시적으로 지정하여 데이터 어긋남 방지
    df['CVD'] = pd.Series(delta, index=df.index).ewm(span=14, adjust=False).mean()
    df['CVD_Signal'] = df['CVD'].rolling(window=9).mean()
    
    # 🚨 핵심 수정: 무자비한 dropna() 대신, 앞부분 50개만 부드럽게 잘라내기
    df = df.iloc[50:].copy()
    
    # 혹시라도 중간에 빈칸이 발생했다면, 이전 캔들의 값으로 채워버림 (오류 방지)
    df.bfill(inplace=True) 
    
    return df

if __name__ == "__main__":
    file_path = '../data/eth_15m_historical.csv' if os.path.exists('../data/eth_15m_historical.csv') else 'data/eth_15m_historical.csv'
    
    if os.path.exists(file_path):
        raw_df = pd.read_csv(file_path, index_col='timestamp', parse_dates=True)
        processed_df = add_indicators(raw_df)
        
        print("\n✅ 지표 계산 완료! 아래는 최근 5개 캔들의 데이터입니다.")
        cols_to_print = ['close', 'RSI_14', 'EMA_50', 'Squeeze_On', 'CVD', 'CVD_Signal']
        # 존재하는 컬럼만 예쁘게 출력
        cols = [c for c in cols_to_print if c in processed_df.columns]
        print(processed_df[cols].tail())
        print(f"\n📊 총 남은 캔들 개수: {len(processed_df)}개 (초기 계산용 50개 컷팅 완료)")
    else:
        print("❌ CSV 파일을 찾을 수 없습니다.")