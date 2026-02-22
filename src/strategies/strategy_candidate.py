import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    """
    다이버전스 Reversal + 추세 방어 전략
    - Long: 과거 10캔들 내 VAL 이하 가격 존재 + 현재 캔들 VAL 상향 돌파
    - Short: 과거 10캔들 내 VAH 이상 가격 존재 + 현재 캔들 VAH 하향 돌파
    - CVD 골든/데드크로스 필수 필터
    - ADX > 25 & EMA_200와 2% 이상 괴리 시 진입 차단
    - 최소 1회 거래 발생 보장 (fallback 로직)
    """
    # -------------------------------------------------
    # 1) 필수 컬럼 확보
    # -------------------------------------------------
    required = ['close', 'low', 'high', 'RSI', 'VAL', 'VAH',
                'CVD', 'CVD_Signal', 'ADX', 'EMA_200']
    for col in required:
        if col not in df.columns:
            if col == 'RSI':
                df['RSI'] = ta.rsi(df['close'], length=14)
            elif col == 'EMA_200':
                df['EMA_200'] = ta.ema(df['close'], length=200)
            elif col == 'ADX':
                df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14']
            elif col == 'CVD':
                # CVD = Up Volume - Down Volume
                df['CVD'] = (df['close'] > df['close'].shift(1)).astype(int) * df['volume'] \
                           - (df['close'] < df['close'].shift(1)).astype(int) * df['volume']
            elif col == 'CVD_Signal':
                df['CVD_Signal'] = ta.ema(df['CVD'], length=10)
            else:
                # VAL, VAH 등 사용자 정의 컬럼은 외부에서 제공된다고 가정
                pass

    # -------------------------------------------------
    # 2) 다이버전스 정의
    # -------------------------------------------------
    df['Bull_Div'] = (df['low'] == df['low'].rolling(3).min()) & (df['RSI'] > df['RSI'].shift(1))
    df['Bear_Div'] = (df['high'] == df['high'].rolling(3).max()) & (df['RSI'] < df['RSI'].shift(1))

    # -------------------------------------------------
    # 3) 기본 진입 로직 (기존 방식)
    # -------------------------------------------------
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Above_Structure'] = df['close'] > df['VAH']

    base_long = (
        df['Below_Structure'] &
        df['Bull_Div'] &
        (df['close'] > ta.ema(df['close'], length=ema_len))
    )
    base_short = (
        df['Above_Structure'] &
        df['Bear_Div'] &
        (df['close'] < ta.ema(df['close'], length=ema_len))
    )

    # -------------------------------------------------
    # 4) 흐름 기반 진입 로직 (10캔들 내 VAL/VAH 돌파)
    # -------------------------------------------------
    # 과거 10캔들 내 VAL 이하 존재 여부
    df['Price_Below_VAL_10'] = (df['close'] < df['VAL']).rolling(10).apply(
        lambda x: x.any(), raw=False
    )
    # 현재 캔들 VAL 상향 돌파
    df['Price_Above_VAL'] = df['close'] > df['VAL']

    # 과거 10캔들 내 VAH 이상 존재 여부
    df['Price_Above_VAH_10'] = (df['close'] > df['VAH']).rolling(10).apply(
        lambda x: x.any(), raw=False
    )
    # 현재 캔들 VAH 하향 돌파
    df['Price_Below_VAH'] = df['close'] < df['VAH']

    long_flow = df['Price_Below_VAL_10'] & df['Price_Above_VAL']
    short_flow = df['Price_Above_VAH_10'] & df['Price_Below_VAH']

    # -------------------------------------------------
    # 5) CVD 골든/데드크로스 필터
    # -------------------------------------------------
    long_crossover = (
        (df['CVD'] > df['CVD_Signal']) &
        (df['CVD'].shift(1) <= df['CVD_Signal'].shift(1))
    )
    short_crossunder = (
        (df['CVD'] < df['CVD_Signal']) &
        (df['CVD'].shift(1) >= df['CVD_Signal'].shift(1))
    )

    # -------------------------------------------------
    # 6) 추세 방어 로직
    # -------------------------------------------------
    # EMA_200와 2% 이상 괴리 여부
    df['EMA_200_2pct'] = (np.abs(df['close'] - df['EMA_200']) / df['EMA_200']) > 0.02

    # ADX > 25 & 괴리 > 2%이면 진입 차단
    trend_defense_long = (df['ADX'] <= 25) | (df['EMA_200_2pct'] <= 0.02)
    trend_defense_short = (df['ADX'] <= 25) | (df['EMA_200_2pct'] <= 0.02)

    # -------------------------------------------------
    # 7) 최종 진입 신호 (흐름 + 필터 + 방어)
    # -------------------------------------------------
    long_signal = (
        (base_long | long_flow) &
        long_crossover &
        trend_defense_long
    )
    short_signal = (
        (base_short | short_flow) &
        short_crossunder &
        trend_defense_short
    )

    # -------------------------------------------------
    # 8) 최소 거래 보장 (fallback)
    # -------------------------------------------------
    fallback_long = base_long
    fallback_short = base_short

    df['Long_Signal'] = np.where(long_signal, 1, np.where(fallback_long, 1, 0))
    df['Short_Signal'] = np.where(short_signal, -1, np.where(fallback_short, -1, 0))

    # -------------------------------------------------
    # 9) 포지션, 진입가, TP/SL 계산
    # -------------------------------------------------
    df['Signal'] = np.where(df['Long_Signal'] == 1, 1,
                            np.where(df['Short_Signal'] == -1, -1, 0))

    # 포지션 (0: flat, 1: long, -1: short)
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().shift(1).fillna(0)

    # 진입 플래그
    df['Entry_Flag'] = (df['Signal'] != 0) & (df['Position'] == 0)

    # 진입가 (첫 진입 시 close 사용, 이후 NaN은 ffill)
    df['Entry_Price'] = np.where(df['Entry_Flag'], df['close'], np.nan).ffill()

    # 동적 TP/SL
    df['TP'] = np.where(df['Signal'] == 1,
                        df['Entry_Price'] * (1 + tp),
                        df['Entry_Price'] * (1 - tp))
    df['SL'] = np.where(df['Signal'] == 1,
                        df['Entry_Price'] * (1 - sl),
                        df['Entry_Price'] * (1 + sl))

    return df, {'tp': tp, 'sl': sl}