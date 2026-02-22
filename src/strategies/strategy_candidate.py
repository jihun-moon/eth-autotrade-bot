import pandas_ta as ta
import numpy as np

def apply_strategy(df, ema_len=30, tp_mult=2.0, sl_mult=1.5):
    """
    SMC(Volume Profile) + CVD + Liquidity Sweep 전략
    - VAL/VAH 외부의 유동성을 터치하고 복귀하는 타점을 포착합니다.
    - 청산 밀집 구역(1940 $, 1995 $) 근처에서 신호를 강화합니다.
    - 펀딩비(0.01 %)를 이용해 롱/숏 신호에 미세 가중치를 부여합니다.
    """
    # --------------------------------------------------------------
    # 1️⃣ ATR 계산 (동적 익절/손절용 – evolve.py 지침 준수)
    # --------------------------------------------------------------
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)

    # --------------------------------------------------------------
    # 2️⃣ 청산 밀집 구역 정의 (절대 tolerance $5)
    # --------------------------------------------------------------
    TOL_LONG = 5.0          # 1940 $ ± $5
    TOL_SHORT = 5.0         # 1995 $ ± $5
    df['Long_Liquidation_Zone'] = (
        (df['close'] >= 1940 - TOL_LONG) &
        (df['close'] <= 1940 + TOL_LONG)
    )
    df['Short_Liquidation_Zone'] = (
        (df['close'] >= 1995 - TOL_SHORT) &
        (df['close'] <= 1995 + TOL_SHORT)
    )

    # --------------------------------------------------------------
    # 3️⃣ 펀딩비 (Normal 0.01 % = 0.0001) → bias factor
    # --------------------------------------------------------------
    FUNDING_RATE = 0.0001          # 0.01 %
    FUNDING_BIAS = 1.0 + FUNDING_RATE * 100   # 1.01

    # --------------------------------------------------------------
    # 4️⃣ 동적 TP / SL 컬럼 생성
    #    - 청산 구역 내이면 TP를 10 % 확대, SL을 10 % 축소
    #    - 구역 외에서는 기본 비율 유지
    # --------------------------------------------------------------
    zone_factor_long = np.where(df['Long_Liquidation_Zone'], 1.1, 1.0)
    zone_factor_short = np.where(df['Short_Liquidation_Zone'], 1.1, 1.0)

    # TP multiplier 조정: 구역 내이면 2.5, 구역 외이면 기본값
    tp_mult_adj = np.where(df['Long_Liquidation_Zone'], 2.5, tp_mult)
    # SL multiplier 조정: 구역 내이면 1.3, 구역 외이면 기본값
    sl_mult_adj = np.where(df['Short_Liquidation_Zone'], 1.3, sl_mult)

    df['target_tp'] = (
        (df['ATR'] * tp_mult_adj / df['close'])
        .fillna(0.02)               # 최소 2 % 확보
        .clip(lower=0.01)           # 최소 1 % 제한
        * zone_factor_long
    )
    df['target_sl'] = (
        (df['ATR'] * sl_mult_adj / df['close'])
        .fillna(0.015)              # 최소 1.5 % 확보
        .clip(lower=0.008)          # 최소 0.8 % 제한
        * zone_factor_short
    )

    # --------------------------------------------------------------
    # 5️⃣ 진입 로직 (이미 계산된 ADX, CVD, VAL, VAH, RSI 활용)
    # --------------------------------------------------------------

    # ── 롱 전략 ──
    # ① Liquidity Sweep
    df['Long_Sweep'] = (df['low'] < df['VAL']) & (df['close'] > df['low'])

    # ② 상승 다이버전스 (RSI 저점 상승)
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))

    # ③ 롱 신호 결합
    df['Long_Signal'] = (
        df['Long_Sweep'] &
        df['Bull_Div'] &
        (df['CVD'] > df['CVD_Signal']) &
        (df['close'] > df['EMA_200'])          # EMA_200 은 이미 존재
    )
    # ④ 시장 강도 필터 (ADX ≤ 30 혹은 장기 추세)
    df['Long_Signal'] = df['Long_Signal'] & (
        (df['ADX'] <= 30) | (df['close'] >= df['EMA_200'])
    )

    # ⑤ 청산 구역 강화
    df['Long_Signal'] = df['Long_Signal'] & df['Long_Liquidation_Zone']

    # ⑥ 펀딩비 bias 적용 (양수 펀딩비 → 롱 신호에 +1 %)
    df['Long_Signal'] = df['Long_Signal'] * FUNDING_BIAS

    # ── 숏 전략 ──
    # ① Liquidity Sweep
    df['Short_Sweep'] = (df['high'] > df['VAH']) & (df['close'] < df['high'])

    # ② 하락 다이버전스 (RSI 고점 하락)
    df['High_3'] = df['high'].rolling(3).max()
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))

    # ③ 숏 신호 결합
    df['Short_Signal'] = (
        df['Short_Sweep'] &
        df['Bear_Div'] &
        (df['CVD'] < df['CVD_Signal']) &
        (df['close'] < df['EMA_200'])
    )
    # ④ 시장 강도 필터
    df['Short_Signal'] = df['Short_Signal'] & (
        (df['ADX'] <= 30) | (df['close'] <= df['EMA_200'])
    )

    # ⑤ 청산 구역 강화
    df['Short_Signal'] = df['Short_Signal'] & df['Short_Liquidation_Zone']

    # ⑥ 펀딩비 bias 적용 (양수 펀딩비 → 숏 신호에 -1 %)
    df['Short_Signal'] = df['Short_Signal'] * (1 / FUNDING_BIAS)

    # --------------------------------------------------------------
    # 6️⃣ 실전용 파라미터 반환
    # --------------------------------------------------------------
    last_tp = df['target_tp'].iloc[-1]
    last_sl = df['target_sl'].iloc[-1]

    return df, {'tp': last_tp, 'sl': last_sl}