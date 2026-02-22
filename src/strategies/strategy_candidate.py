# --------------------------------------------------------------
# 1️⃣ 라이브러리 임포트
# --------------------------------------------------------------
import numpy as np
import pandas as pd
import pandas_ta as ta               # TA‑library (EMA, ADX, RSI 등)
import vectorbt as vbt               # vectorbt core
from vectorbt.signals import Signal # 신호 객체
from vectorbt.pro import Pro        # (선택) ATR 등 고급 기능
# --------------------------------------------------------------

def apply_strategy(df: pd.DataFrame,
                   ema_len: int = 30,
                   tp: float = 0.02,          # 2% 목표 수익
                   sl: float = 0.015,         # 1.5% 손절
                   adx_len: int = 14,
                   lookback_len: int = 5,
                   use_dynamic_sl: bool = False) -> tuple[pd.DataFrame, dict]:
    """
    다이버전스 + 매물대(VAL/VAH) 전략 – 벡터‑베이스 구현
    -------------------------------------------------
    - VAL, VAH, CVD, CVD_Signal 컬럼은 이미 존재한다고 가정
    - LONG : VAL 하향 이탈 + Bullish Divergence + CVD > CVD_Signal
               (ADX ≤ 25 OR price ≥ EMA)
    - SHORT: VAH 상향 이탈 + Bearish Divergence + CVD < CVD_Signal
               (ADX ≤ 25 OR price ≤ EMA)
    - TP/SL 비율 적용, 동적 SL(ATR 기반) 옵션 제공
    - vectorbt 사용 시 `leverage` 파라미터는 전혀 쓰지 않음 (기본 1)
    반환값:
        df : 원본에 Signal, Position, ExitSignal 컬럼이 추가된 DataFrame
        cfg: 설정값 (tp, sl, …)
    """
    # --------------------------------------------------------------
    # 2️⃣ 필수 컬럼 체크 (중복 방지)
    # --------------------------------------------------------------
    required = ['VAL', 'VAH', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200', 'RSI']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"필요한 컬럼이 누락되었습니다: {missing}")

    # --------------------------------------------------------------
    # 3️⃣ EMA 재계산 (필요 시 기존 EMA_200 대신 동적 EMA 사용)
    # --------------------------------------------------------------
    # 기존 EMA_200 가 있으면 그대로 사용하고, 없으면 새로 계산
    if 'EMA_200' in df.columns:
        df['EMA'] = df['EMA_200']
    else:
        df['EMA'] = df['close'].ewm(span=ema_len, adjust=False).mean()

    # --------------------------------------------------------------
    # 4️⃣ 다이버전스 지표 (Bullish / Bearish)
    # --------------------------------------------------------------
    # 5‑bar look‑back minima / maxima (한 번만 계산 → 재사용)
    low_lookback = df['low'].rolling(window=lookback_len).min()
    high_lookback = df['high'].rolling(window=lookback_len).max()

    # Bullish divergence: 현재 저점이 look‑back 저점 이하이고 RSI 상승
    df['Bull_Div'] = (df['low'] <= low_lookback) & (df['RSI'] > df['RSI'].shift(1))

    # Bearish divergence: 현재 고점이 look‑back 고점 이상이고 RSI 하락
    df['Bear_Div'] = (df['high'] >= high_lookback) & (df['RSI'] < df['RSI'].shift(1))

    # --------------------------------------------------------------
    # 5️⃣ 매물대(VAL/VAH) 돌파 여부
    # --------------------------------------------------------------
    df['Below_Structure'] = df['close'] < df['VAL']          # VAL 하향 이탈
    df['Above_Structure'] = df['close'] > df['VAH']          # VAH 상향 이탈

    # --------------------------------------------------------------
    # 6️⃣ 진입 로직 (Long / Short)
    # --------------------------------------------------------------
    # LONG 진입 조건
    long_entry = (
        df['Below_Structure'] &
        df['Bull_Div'] &
        (df['CVD'] > df['CVD_Signal']) &
        ((df['ADX'] <= 25) | (df['close'] >= df['EMA']))   # ADX ≤ 25 혹은 EMA 위
    )

    # SHORT 진입 조건
    short_entry = (
        df['Above_Structure'] &
        df['Bear_Div'] &
        (df['CVD'] < df['CVD_Signal']) &
        ((df['ADX'] <= 25) | (df['close'] <= df['EMA']))   # ADX ≤ 25 혹은 EMA 아래
    )

    # --------------------------------------------------------------
    # 7️⃣ Signal 생성 (vectorbt.Signal 활용)
    # --------------------------------------------------------------
    # 0 = No position, 1 = Long, -1 = Short
    # 진입 신호가 동시에 발생하지 않도록 우선순위 지정
    df['Entry_Signal'] = np.where(long_entry, 1,
                          np.where(short_entry, -1, 0))

    # Lag=1 로 한 바(bar) 뒤에 포지션을 잡도록 shift
    df['Position'] = vbt.signals.shift(df['Entry_Signal'], lag=1)

    # --------------------------------------------------------------
    # 8️⃣ TP/SL 로직
    # --------------------------------------------------------------
    # 고정 TP/SL 비율 (절대 가격)
    df['TP'] = df['close'] * (1 + tp)   # 목표가격
    df['SL'] = df['close'] * (1 - sl)   # 손절가격

    # 동적 SL (ATR 기반) – 옵션 플래그에 따라 활성화
    if use_dynamic_sl:
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        # ATR * 2 로 동적 손절 구간을 잡는다.
        df['SL_Dynamic'] = df['close'] - df['ATR'] * 2

    # Exit 시그널 생성
    # (1) 고정 SL : price <= SL
    # (2) 동적 SL : price <= SL_Dynamic (if 사용)
    # (3) 목표 TP : price >= TP
    exit_long = (
        (df['Position'] == 1) &
        ((df['close'] >= df['TP']) |
         ((use_dynamic_sl) & (df['close'] <= df['SL_Dynamic'])))
    )
    exit_short = (
        (df['Position'] == -1) &
        ((df['close'] <= df['SL']) |
         ((use_dynamic_sl) & (df['close'] >= df['SL_Dynamic'])))
    )

    # Lag=1 로 청산 시점이 다음 바가 되도록 shift
    df['Exit_Long'] = vbt.signals.shift(exit_long, lag=1)
    df['Exit_Short'] = vbt.signals.shift(exit_short, lag=1)

    # 최종 Exit 시그널 (포지션이 바뀐 시점에 0 으로 전환)
    df['Exit_Signal'] = np.where(df['Exit_Long'], -1,
                          np.where(df['Exit_Short'], 1, 0))

    # 포지션을 Exit 시점 바로 뒤에 0 으로 바꾸는 lag‑1 적용
    df['Position'] = vbt.signals.shift(df['Exit_Signal'], lag=1)

    # --------------------------------------------------------------
    # 9️⃣ 최종 컬럼 정리
    # --------------------------------------------------------------
    # Signal 컬럼을 명시적으로 반환 (entry 신호만 포함)
    df['Signal'] = df['Entry_Signal']

    # 설정값 반환 (백테스트에 그대로 사용 가능)
    cfg = {'ema_len': ema_len, 'tp': tp, 'sl': sl,
           'adx_len': adx_len, 'lookback_len': lookback_len,
           'use_dynamic_sl': use_dynamic_sl}
    return df, cfg