import numpy as np
import pandas as pd
import pandas_ta as ta

def apply_strategy(df):
    """
    다이버전스 + 매물대 상하단 전략 – 개선된 버전
    - VAL/VAH 및 POC 기반 가격 구간 필터
    - 5‑바 저·고점 lookback을 이용한 다이버전스
    - CVD 상승/하락 신호
    - ADX ≤ 25 로 추세 강도 억제
    - EMA20과 EMA200 교차 필터 (추세 방향)
    - 5‑바 평균 대비 20% 이상 거래량 필터
    - ATR 기반 동적 TP/SL + 누적 ATR 기반 트레일링 스톱
    반환값: (수정된 DataFrame, 전략 파라미터 딕셔너리)
    """
    # ------------------- 파라미터 -------------------
    tp = 0.02          # 정적 TP 비율
    sl = 0.015         # 정적 SL 비율
    adx_thresh = 25
    atr_len = 14
    atr_factor = 1.5
    vol_len = 5
    vol_factor = 1.2
    tp_factor = 2.0
    sl_factor = 2.0

    # ------------------- 핵심 지표 -------------------
    df['EMA_200'] = ta.ema(df['close'], length=200)
    df['EMA_20']  = ta.ema(df['close'], length=20)

    df['RSI'] = ta.rsi(df['close'], length=14)

    df['ADX'] = ta.adx(df['high'], df['low'], df['close'], length=14)

    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=atr_len)

    df['Low_Lookback'] = df['low'].rolling(window=vol_len).min().fillna(df['low'])
    df['High_Lookback'] = df['high'].rolling(window=vol_len).max().fillna(df['high'])

    df['CVD_Signal'] = df['CVD'].shift(1).fillna(df['CVD'])

    df['Vol_Filter'] = df['volume'] > df['volume'].rolling(window=vol_len).mean() * vol_factor

    df['EMA_20_Up']  = df['EMA_20'] > df['EMA_200']
    df['EMA_20_Down'] = df['EMA_20'] < df['EMA_200']

    df['Bull_Div'] = (df['low'] <= df['Low_Lookback']) & (df['RSI'] > df['RSI'].shift(1))
    df['Bear_Div'] = (df['high'] >= df['High_Lookback']) & (df['RSI'] < df['RSI'].shift(1))

    # ------------------- 롱/숏 진입 조건 -------------------
    long_criteria = (
        (df['close'] < df['VAL'] * 1.001) &               # VAL 아래
        df['Bull_Div'] &                                 # 저점 다이버전스
        (df['CVD'] > df['CVD_Signal']) &                # CVD 상승
        (df['ADX'] <= adx_thresh) &                     # ADX 낮은 구간
        df['EMA_20_Up'] &                                # EMA20 > EMA200 (상승 추세)
        df['Vol_Filter'] &                               # 거래량 필터
        (df['close'] < df['POC'])                        # POC 아래
    )
    short_criteria = (
        (df['close'] > df['VAH'] * 0.999) &               # VAH 위
        df['Bear_Div'] &                                 # 고점 다이버전스
        (df['CVD'] < df['CVD_Signal']) &                # CVD 하락
        (df['ADX'] <= adx_thresh) &                     # ADX 낮은 구간
        df['EMA_20_Down'] &                              # EMA20 < EMA200 (하락 추세)
        df['Vol_Filter'] &                               # 거래량 필터
        (df['close'] > df['POC'])                        # POC 위
    )
    long_criteria = long_criteria.fillna(False)
    short_criteria = short_criteria.fillna(False)

    df['Long_Signal']  = long_criteria
    df['Short_Signal'] = short_criteria

    # ------------------- 최종 포지션 시그널 -------------------
    df['Signal'] = np.where(df['Long_Signal'], 1,
                            np.where(df['Short_Signal'], -1, 0))

    # ------------------- 포지션 오픈 -------------------
    df['Open_Long']  = (df['Signal'] == 1) & (df['Signal'].shift(1) == 0)
    df['Open_Short'] = (df['Signal'] == -1) & (df['Signal'].shift(1) == 0)

    df['Entry_Price'] = np.where(df['Open_Long'] | df['Open_Short'], df['close'], np.nan)
    df['Entry_Price'] = df['Entry_Price'].ffill()   # 포지션 유지 시 가격 유지

    # ------------------- 동적 TP/SL + 정적 fallback -------------------
    df['TP'] = np.where(df['Entry_Price'].notna(),
                        df['Entry_Price'] * (1 + tp_factor * df['ATR']),
                        np.nan)
    df['SL'] = np.where(df['Entry_Price'].notna(),
                        df['Entry_Price'] * (1 - sl_factor * df['ATR']),
                        np.nan)

    # 초기 NaN을 정적 TP/SL 로 채움
    df['TP'] = df['TP'].fillna(df['Entry_Price'] * (1 + tp))
    df['SL'] = df['SL'].fillna(df['Entry_Price'] * (1 - sl))

    # ------------------- TP / SL 탈출 -------------------
    df['Exit_TP'] = (df['Signal'] == 1) & (df['close'] >= df['TP'])
    df['Exit_SL'] = (df['Signal'] == -1) & (df['close'] <= df['SL'])

    # ------------------- 누적 ATR 기반 트레일링 스톱 -------------------
    df['Trailing_Stop'] = np.where(df['Entry_Price'].notna(),
                                   np.where(df['Signal'] == 1,
                                           df['Entry_Price'] - df['ATR'].cummax() * atr_factor,
                                           np.where(df['Signal'] == -1,
                                                   df['Entry_Price'] + df['ATR'].cummax() * atr_factor,
                                                   np.nan)),
                                   np.nan)

    df['Exit_Trailing'] = ((df['Signal'] == 1) & (df['close'] <= df['Trailing_Stop'])) | \
                         ((df['Signal'] == -1) & (df['close'] >= df['Trailing_Stop']))

    df['Exit'] = df['Exit_TP'] | df['Exit_SL'] | df['Exit_Trailing']

    # ------------------- 포지션 규모 (선택) -------------------
    df['Position_Size'] = np.where(df['Signal'] == 1, 1,
                                  np.where(df['Signal'] == -1, -1, 0))

    # ------------------- 파라미터 딕셔너리 -------------------
    params = {
        'tp': tp,
        'sl': sl,
        'adx_thresh': adx_thresh,
        'atr_len': atr_len,
        'atr_factor': atr_factor,
        'vol_len': vol_len,
        'vol_factor': vol_factor,
        'tp_factor': tp_factor,
        'sl_factor': sl_factor,
        'ema_len_200': 200,
        'ema_len_20': 20,
        'rsi_len': 14,
        'entry_filter': 'VAL/VAH + divergence + CVD + ADX + EMA20/200 cross + volume',
        'exit_filter': 'TP/SL + trailing stop',
        'signal_column': 'Signal',
        'open_long_col': 'Open_Long',
        'open_short_col': 'Open_Short',
        'entry_price_col': 'Entry_Price',
        'tp_col': 'TP',
        'sl_col': 'SL',
        'trailing_stop_col': 'Trailing_Stop',
        'exit_col': 'Exit',
        'position_size_col': 'Position_Size',
    }

    return df, params