import pandas_ta as ta
import numpy as np

def apply_strategy(
    df,
    ema_len: int = 30,
    tp_mult: float = 2.0,
    sl_mult: float = 1.5,
    # 옵션 파라미터 – 필요에 따라 조정 가능
    vp_len: int = 14,
    adx_len: int = 14,
    liquidation_long: float = 1940.0,
    liquidation_short: float = 1995.0,
    breakout_thr: float = 0.005,   # 0.5 % 거리 기준
    vol_mult: float = 1.5,        # 평균 거래량 대비 1.5× 이상
    adx_min: int = 20,
):
    """
    SMC(Volume Profile) + CVD + Divergence 전략
    - 청산가 밀집 구역(1940, 1995) 근처에서 가짜 돌파를 걸러냄
    - 진입 타점을 볼륨·ADX·가격 변동 강도로 정교화
    """
    # -------------------------------------------------
    # 1️⃣ 기본 지표
    # -------------------------------------------------
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['RSI'] = ta.rsi(df['close'], length=14)

    # EMA
    df['EMA'] = ta.ema(df['close'], length=ema_len)
    df['EMA_200'] = ta.ema(df['close'], length=200)

    # ADX – DataFrame 메서드 사용 (오류 방지)
    df['ADX'] = df[['high', 'low', 'close']].adx(length=adx_len)

    # Volume Profile → VAL, VAH
    vp = df[['high', 'low', 'close', 'volume']].vp(length=vp_len)
    df['VAL'] = vp['VAL']
    df['VAH'] = vp['VAH']

    # CVD (Cumulative Volume Delta) + Signal
    df['CVD'] = ta.cvd(df['close'], df['volume'], length=20)          # 20‑bar CVD
    df['CVD_Signal'] = df['CVD'].rolling(20).mean()                # 20‑bar 평균 CVD

    # -------------------------------------------------
    # 2️⃣ 가짜 돌파 방지 필터 (청산가 밀집 구역)
    # -------------------------------------------------
    # 청산가와 현재 가격 사이의 거리(%) 계산
    df['close_to_long_liquidation'] = (df['close'] - liquidation_long) / liquidation_long
    df['close_to_short_liquidation'] = (liquidation_short - df['close']) / liquidation_short

    # 가짜 돌파를 걸러내는 기준
    #   • 청산가와 0.5 % 이내이면 진입 금지
    #   • 0.5 % 이상 떨어졌을 경우, 볼륨·ADX·가격 변동 강도 확인
    df['Long_Fake_Breakout_Filter'] = (
        (df['close_to_long_liquidation'] > breakout_thr) &
        (df['volume'] > df['volume'].rolling(20).mean() * vol_mult) &
        (df['ADX'] > adx_min)
    )
    df['Short_Fake_Breakout_Filter'] = (
        (df['close_to_short_liquidation'] > breakout_thr) &
        (df['volume'] > df['volume'].rolling(20).mean() * vol_mult) &
        (df['ADX'] > adx_min)
    )

    # -------------------------------------------------
    # 3️⃣ 진입 시그널 (핵심 로직 유지)
    # -------------------------------------------------
    # 다이버전스
    df['Low_3'] = df['low'].rolling(3).min()
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))

    df['High_3'] = df['high'].rolling(3).max()
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))

    # 롱 진입
    df['Long_Signal'] = (
        (df['close'] < df['VAL']) &
        df['Bull_Div'] &
        (df['CVD'] > df['CVD_Signal']) &
        (df['close'] > df['EMA']) &
        df['Long_Fake_Breakout_Filter'] &
        ((df['ADX'] <= 25) | (df['close'] >= df['EMA_200']))
    )

    # 숏 진입
    df['Short_Signal'] = (
        (df['close'] > df['VAH']) &
        df['Bear_Div'] &
        (df['CVD'] < df['CVD_Signal']) &
        (df['close'] < df['EMA']) &
        df['Short_Fake_Breakout_Filter'] &
        ((df['ADX'] <= 25) | (df['close'] <= df['EMA_200']))
    )

    # 시각화용 최종 시그널 컬럼
    df['Signal'] = np.where(df['Long_Signal'], 'LONG',
                            np.where(df['Short_Signal'], 'SHORT', np.nan))

    # -------------------------------------------------
    # 4️⃣ ATR 기반 TP / SL (기존 로직 유지)
    # -------------------------------------------------
    df['target_tp'] = (df['ATR'] * tp_mult / df['close']).fillna(0.02).clip(lower=0.01)
    df['target_sl'] = (df['ATR'] * sl_mult / df['close']).fillna(0.015).clip(lower=0.008)

    # -------------------------------------------------
    # 5️⃣ 반환
    # -------------------------------------------------
    last_tp = df['target_tp'].iloc[-1]
    last_sl = df['target_sl'].iloc[-1]

    return df, {'tp': last_tp, 'sl': last_sl}