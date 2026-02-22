import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    """
    개선된 다이버전스 Reversal 전략
    - 가격이 VAL/VAH를 이탈 후 복귀하는 순간을 진입 신호로 활용
    - CVD와 ADX를 이용한 수급·추세 필터 적용
    - 0회 거래 현상 방지를 위해 진입 조건을 유연하게 설계
    """
    # 필수 컬럼 존재 여부 확인 및 필요 시 계산
    required = ['close', 'low', 'high', 'RSI', 'VAL', 'VAH', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200']
    for col in required:
        if col not in df.columns:
            if col == 'RSI':
                df[col] = ta.rsi(df['close'], length=14)
            if col == 'EMA_200':
                df[col] = ta.ema(df['close'], length=200)

    # VAL/VAH 이탈·복귀를 위한 버퍼 (0.1%)
    val_low  = df['VAL'] * 1.001   # VAL 아래 이탈
    vah_high = df['VAH'] * 0.999   # VAH 위 이탈

    # ---------- Long 진입 ----------
    # 1) VAL 아래로 이탈
    df['Long_Below'] = df['close'] <= val_low
    df['Long_Below_Cross'] = df['Long_Below'] & (~df['Long_Below'].shift(1))

    # 2) VAL 위로 복귀
    df['Long_Above'] = df['close'] > val_low
    df['Long_Above_Cross'] = df['Long_Above'] & (~df['Long_Above'].shift(1))

    df['Long_Cross'] = df['Long_Below_Cross'] & df['Long_Above_Cross']

    # ---------- Short 진입 ----------
    # 1) VAH 위로 이탈
    df['Short_Above'] = df['close'] >= vah_high
    df['Short_Above_Cross'] = df['Short_Above'] & (~df['Short_Above'].shift(1))

    # 2) VAH 아래로 복귀
    df['Short_Below'] = df['close'] < vah_high
    df['Short_Below_Cross'] = df['Short_Below'] & (~df['Short_Below'].shift(1))

    df['Short_Cross'] = df['Short_Above_Cross'] & df['Short_Below_Cross']

    # ---------- 수급 필터 ----------
    # CVD 골든크로스 / 데드크로스
    df['CVD_cross_up']   = (df['CVD'] > df['CVD_Signal']) & (df['CVD'].shift(1) <= df['CVD_Signal'])
    df['CVD_cross_down'] = (df['CVD'] < df['CVD_Signal']) & (df['CVD'].shift(1) >= df['CVD_Signal'])

    # ---------- ADX·EMA_200 거리 필터 ----------
    # ADX >= 25
    df['ADX_Filter'] = df['ADX'] >= 25

    # EMA_200과의 거리 (2% 기준)
    price_diff = df['close'] - df['EMA_200']
    df['Price_Far'] = price_diff.abs() > df['close'] * 0.02

    # 역추세 진입 방지 (가격이 EMA_200에서 멀리 떨어져 있을 때)
    df['ADX_Filter_Long']  = df['ADX_Filter'] & (~df['Price_Far'])
    df['ADX_Filter_Short'] = df['ADX_Filter'] & (~df['Price_Far'])

    # ---------- 최종 신호 ----------
    df['Long_Signal']  = df['Long_Cross'] & df['CVD_cross_up'] & df['ADX_Filter_Long']
    df['Short_Signal'] = df['Short_Cross'] & df['CVD_cross_down'] & df['ADX_Filter_Short']

    # 시스템 연동
    df['Signal'] = np.where(df['Long_Signal'], 1,
                     np.where(df['Short_Signal'], -1, 0))

    # 진입 플래그: 0 → 비0 전환 시점
    df['Entry_Flag'] = (df['Signal'] != 0) & (df['Signal'].shift(1) == 0)

    # 진입 가격 기록 (NaN → 실제 가격 → forward fill)
    df['Entry_Price'] = np.nan
    df.loc[df['Entry_Flag'], 'Entry_Price'] = df['close']
    df['Entry_Price'] = df['Entry_Price'].ffill()

    # TP / SL
    df['TP'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 + tp), np.nan)
    df['SL'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 - sl), np.nan)
    df['TP'] = np.where(df['Signal'] == -1, df['Entry_Price'] * (1 - tp), df['TP'])
    df['SL'] = np.where(df['Signal'] == -1, df['Entry_Price'] * (1 + sl), df['SL'])

    # 포지션 트래킹
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().shift(1).fillna(0)

    return df, {'tp': tp, 'sl': sl}