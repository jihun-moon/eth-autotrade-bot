import numpy as np
import pandas as pd

def apply_strategy(df):
    """
    다이버전스 + 매물대 상하단 전략 (개선 버전)
    - 기존 지표(RSSI, EMA_200, ADX, VAL/VAH, POC, CVD, Squeeze_On 등)는
      `indicators.py`에서 미리 계산된 상태를 가정합니다.
    - 파라미터를 함수 시그니처에 노출하지 않으며, 내부에서 고정값을 사용합니다.
    - 시그널 생성 시 각 조건을 명확히 괄호로 감싸 TypeError 방지를 보장합니다.
    """
    # 1️⃣ 필수 컬럼 존재 여부 확인
    required = [
        'close', 'low', 'high', 'VAL', 'VAH', 'POC',
        'CVD', 'CVD_Signal', 'RSI', 'ADX', 'EMA_200',
        'Squeeze_On', 'volume'
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # 2️⃣ 고정 파라미터 (함수 시그니처에 노출되지 않음)
    tp = 0.02   # Take‑Profit 비율
    sl = 0.015  # Stop‑Loss 비율

    # 3️⃣ 다이버전스 탐지를 위한 Look‑back 값
    df['Low_Lookback'] = df['low'].rolling(window=5).min()
    df['High_Lookback'] = df['high'].rolling(window=5).max()
    df['Low_Lookback'].fillna(df['low'], inplace=True)
    df['High_Lookback'].fillna(df['high'], inplace=True)

    # 4️⃣ 가격 구조 이탈 감지 (허용 오차 확대)
    df['Below_Structure'] = df['close'] < (df['VAL'] * 1.002)
    df['Above_Structure']  = df['close'] > (df['VAH'] * 0.998)

    # 5️⃣ RSI 기반 다이버전스 + 필터 (RSI 50 초과/미만)
    df['Bull_Div'] = (
        (df['low'] <= df['Low_Lookback']) &
        (df['RSI'] > df['RSI'].shift(1)) &
        (df['RSI'] > 50)
    )
    df['Bear_Div'] = (
        (df['high'] >= df['High_Lookback']) &
        (df['RSI'] < df['RSI'].shift(1)) &
        (df['RSI'] < 50)
    )

    # 6️⃣ EMA 기반 단기·중기 추세 필터
    df['EMA_20']  = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50']  = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA_20'].fillna(df['close'], inplace=True)
    df['EMA_50'].fillna(df['close'], inplace=True)

    df['EMA_20_50_Uptrend'] = (df['EMA_20'] < df['EMA_50'])
    df['Long_EMA_Filter'] = df['EMA_20_50_Uptrend'] & (df['close'] > df['EMA_20'])
    df['Short_EMA_Filter'] = (~df['EMA_20_50_Uptrend']) & (df['close'] < df['EMA_20'])

    # 7️⃣ 볼륨 필터 (5일 평균 대비 20% 이상)
    df['Vol_5MA'] = df['volume'].rolling(window=5).mean()
    df['Vol_Filter'] = df['volume'] > df['Vol_5MA'] * 1.2

    # 8️⃣ Bollinger Band 필터 (극단적 가격 배제)
    df['SMA_20'] = df['close'].rolling(window=20).mean()
    df['STD_20'] = df['close'].rolling(window=20).std()
    df['BB_Upper'] = df['SMA_20'] + 2 * df['STD_20']
    df['BB_Lower'] = df['SMA_20'] - 2 * df['STD_20']
    df['BB_Upper'].fillna(df['close'], inplace=True)
    df['BB_Lower'].fillna(df['close'], inplace=True)
    df['BB_Upper_Filter'] = df['close'] > df['BB_Upper']
    df['BB_Lower_Filter'] = df['close'] < df['BB_Lower']

    # 9️⃣ POC 근접 필터 (최근 10일 평균 변동폭 대비 2% 이내)
    df['POC_Filter'] = abs(df['close'] - df['POC']) < df['close'].rolling(10).mean() * 0.02

    # 🔟 Squeeze 필터 (불리언 강제 변환)
    if not pd.api.types.is_bool_dtype(df['Squeeze_On']):
        df['Squeeze_On'] = df['Squeeze_On'].astype(bool)

    # 1️⃣1️⃣ 롱 시그널 조합
    long_signal = (
        df['Below_Structure'] &
        df['Bull_Div'] &
        df['CVD'] > df['CVD_Signal'] &
        df['Squeeze_On'] &
        df['Vol_Filter'] &
        df['Long_EMA_Filter'] &
        df['BB_Upper_Filter'] &
        ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))
    )
    df['Long_Signal'] = long_signal.astype(bool)

    # 1️⃣2️⃣ 숏 시그널 조합
    short_signal = (
        df['Above_Structure'] &
        df['Bear_Div'] &
        df['CVD'] < df['CVD_Signal'] &
        df['Squeeze_On'] &
        df['Vol_Filter'] &
        df['Short_EMA_Filter'] &
        df['BB_Lower_Filter'] &
        ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))
    )
    df['Short_Signal'] = short_signal.astype(bool)

    # 1️⃣3️⃣ 최종 시그널 컬럼 (1: 롱, -1: 숏, 0: 무신호)
    df['Signal'] = np.where(df['Long_Signal'], 1,
                    np.where(df['Short_Signal'], -1, 0))

    # 1️⃣4️⃣ 파라미터 반환
    params = {'tp': tp, 'sl': sl}
    return df, params