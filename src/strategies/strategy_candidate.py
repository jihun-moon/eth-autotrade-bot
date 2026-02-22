import pandas as pd
import pandas_ta as ta
import numpy as np   # 향후 수치 연산에 활용 가능

def apply_strategy(df: pd.DataFrame, ema_len: int = 30) -> tuple[pd.DataFrame, dict]:
    """
    매매 전략 적용 함수
    - ATR, EMA_200, ADX, RSI, VAL, VAH, CVD, CVD_Signal 등 주요 지표를 계산
    - Bull/Bear divergence와 CVD divergence를 이용해 롱/숏 시그널 생성
    - ADX와 EMA_200을 리스크 필터로 사용
    - 최종 반환값은 고정된 TP/SL (tp=0.02, sl=0.015) 로 고정
    """
    # -------------------------------------------------
    # 1️⃣ 기본 지표 계산
    # -------------------------------------------------
    # ATR (14일)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14).atr

    # EMA_200 (200일)
    df['EMA_200'] = ta.ema(df['close'], length=200).ema

    # ADX (14일)
    adx_len = 14
    df['ADX'] = ta.adx(df['high'], df['low'], df['close'], length=adx_len).adx

    # RSI (14일)
    rsi_len = 14
    df['RSI'] = ta.rsi(df['close'], length=rsi_len).rsi

    # Value‑Area Low / High (VAL, VAH) (14일)
    val_len = 14
    df['VAL'] = ta.val(df['high'], df['low'], df['close'], length=val_len).val
    df['VAH'] = ta.vah(df['high'], df['low'], df['close'], length=val_len).vah

    # CVD (Commodity Volume Divergence) 및 CVD_Signal (14일)
    cvd_len = 14
    df['CVD'] = ta.cvd(df['close'], df['volume'], length=cvd_len).cvd
    df['CVD_Signal'] = ta.cvd(df['close'], df['volume'], length=cvd_len).cvd_signal

    # -------------------------------------------------
    # 2️⃣ 구조 기반 시그널 (Low_3 / High_3)
    # -------------------------------------------------
    df['Low_3'] = df['low'].rolling(3).min()
    df['High_3'] = df['high'].rolling(3).max()

    df['Below_Structure'] = df['close'] < df['VAL']
    df['Above_Structure'] = df['close'] > df['VAH']

    # Bull / Bear divergence
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))

    # -------------------------------------------------
    # 3️⃣ 롱 / 숏 시그널 생성
    # -------------------------------------------------
    # EMA (전략 파라미터)
    df['EMA'] = ta.ema(df['close'], length=ema_len).ema

    # 롱 시그널
    df['Long_Signal'] = (
        df['Below_Structure'] &
        df['Bull_Div'] &
        (df['CVD'] > df['CVD_Signal']) &
        (df['close'] > df['EMA'])
    ) & ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))

    # 숏 시그널
    df['Short_Signal'] = (
        df['Above_Structure'] &
        df['Bear_Div'] &
        (df['CVD'] < df['CVD_Signal']) &
        (df['close'] < df['EMA'])
    ) & ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))

    # -------------------------------------------------
    # 4️⃣ 동적 TP/SL 계산 (예시) – 실제 반환값은 고정값으로 교체
    # -------------------------------------------------
    # 마지막 ATR와 종가를 이용해 TP/SL을 구하지만, 요구사항에 따라
    # 최종 반환값은 고정된 0.02 / 0.015 로 강제합니다.
    last_atr = df['ATR'].iloc[-1] if 'ATR' in df.columns else 0.01
    last_close = df['close'].iloc[-1]
    d_tp = (last_atr * 2.0) / last_close
    d_sl = (last_atr * 1.5) / last_close

    # -------------------------------------------------
    # 5️⃣ 최종 반환 (고정 TP/SL)
    # -------------------------------------------------
    return df, {'tp': 0.02, 'sl': 0.015}