import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015,
                  atr_len=14, vol_factor=0.5, max_pos=1):
    """
    개선된 다이버전스 + 매물대/구조 전략
    
    Parameters
    ----------
    df : pd.DataFrame
        입력 데이터프레임은 다음 컬럼을 이미 포함하고 있다고 가정합니다.
        - open, high, low, close, volume
        - VAL, VAH, POC, CVD, CVD_Signal, ADX, Squeeze_On, EMA_200
    ema_len : int
        단기 EMA 길이 (롱/숏 진입 확인용)
    tp : float
        고정 목표 이익 비율 (ATR 기반 TP/SL 사용 시 무시됩니다)
    sl : float
        고정 손절 비율 (ATR 기반 TP/SL 사용 시 무시됩니다)
    atr_len : int
        ATR 계산에 사용할 기간. 0이면 ATR 기반 TP/SL을 사용하지 않습니다.
    vol_factor : float
        20일 평균 거래량 대비 최소 거래량 필터 비율
    max_pos : int
        동시에 보유할 수 있는 최대 포지션 수 (예: 1 = 단일 포지션)

    Returns
    -------
    tuple
        (df, params_dict) – 수정된 데이터프레임과 파라미터 딕셔너리
    """
    # ---------- 1️⃣ 다이버전스 탐지 ----------
    df['Low_Lookback'] = df['low'].rolling(window=5).min()
    df['High_Lookback'] = df['high'].rolling(window=5).max()
    df['Bull_Div'] = (df['low'] <= df['Low_Lookback']) & (df['RSI'] > df['RSI'].shift(1))
    df['Bear_Div'] = (df['high'] >= df['High_Lookback']) & (df['RSI'] < df['RSI'].shift(1))

    # ---------- 2️⃣ 기본 진입 필터 ----------
    df['Below_Structure'] = df['close'] < (df['VAL'] * 1.001)
    df['Above_Structure'] = df['close'] > (df['VAH'] * 0.999)

    # EMA 교차 (단기 EMA > 장기 EMA)
    df['EMA_short'] = df['close'].ta.ema(span=ema_len)
    df['EMA_long'] = df['close'].ta.ema(span=ema_len * 3)
    df['EMA_cross'] = (df['EMA_short'] > df['EMA_long']) & (df['EMA_short'].shift(1) <= df['EMA_long'].shift(1))

    # ADX 강도 필터 (트렌드 확인)
    df['ADX_filter'] = (df['ADX'] > 25) | (df['close'] >= df['EMA_200'])

    # 거래량 필터 (20일 평균 대비 최소 비율)
    df['Volume_Filter'] = df['volume'] > (df['volume'].rolling(window=20).mean() * vol_factor)

    # Bollinger‑Band‑like Squeeze 해제 감지
    df['Squeeze_Release'] = (df['Squeeze_On'] < 0) & (df['Squeeze_On'].shift(1) >= 0)

    # ---------- 3️⃣ 롱 / 숏 진입 ----------
    # 롱 진입 조건
    long_entry = (
        df['Below_Structure'] &
        df['Bull_Div'] &
        df['CVD'] > df['CVD_Signal'] &
        df['EMA_cross'] &
        df['ADX_filter'] &
        df['Volume_Filter'] &
        df['Squeeze_Release']
    )
    df['Long_Signal'] = long_entry

    # 숏 진입 조건
    short_entry = (
        df['Above_Structure'] &
        df['Bear_Div'] &
        df['CVD'] < df['CVD_Signal'] &
        df['EMA_cross'] &
        (df['ADX'] < 25) |
        (df['close'] <= df['EMA_200']) &
        df['Volume_Filter'] &
        df['Squeeze_Release']
    )
    df['Short_Signal'] = short_entry

    # ---------- 4️⃣ 포지션 관리 ----------
    # 포지션 누적 카운터 (max_pos 제한)
    df['Long_Pos'] = df['Long_Signal'].cumsum()
    df['Short_Pos'] = df['Short_Signal'].cumsum()
    df['Position'] = np.where(df['Long_Pos'] > max_pos, 0,
                              np.where(df['Short_Pos'] > max_pos, 0,
                                       np.where(df['Long_Signal'], 1,
                                               np.where(df['Short_Signal'], -1, 0))))

    # 방향(1, -1, 0)
    df['Direction'] = np.sign(df['Position'])

    # ---------- 5️⃣ ATR 기반 TP/SL ----------
    if atr_len > 0:
        df['ATR'] = df['close'].ta.atr(length=atr_len)
        df['TP'] = df['close'] + df['ATR'] * df['Direction'] * tp
        df['SL'] = df['close'] - df['ATR'] * df['Direction'] * sl
    else:
        df['TP'] = np.nan
        df['SL'] = np.nan

    # ---------- 6️⃣ 트레일링 스톱 ----------
    df['Trailing_Stop'] = np.where(
        df['Position'] == 1,
        df['close'].rolling(window=5).min() - df['ATR'] * 0.5,
        np.where(
            df['Position'] == -1,
            df['close'].rolling(window=5).max() + df['ATR'] * 0.5,
            np.nan
        )
    )

    # ---------- 7️⃣ 청산 조건 ----------
    # TP / SL 청산
    df['Exit_TP'] = (df['Position'] == 1) & (df['close'] >= df['TP'])
    df['Exit_SL'] = (df['Position'] == -1) & (df['close'] <= df['SL'])

    # 트레일링 스톱 청산
    df['Exit_TS'] = (
        (df['Position'] == 1) & (df['close'] <= df['Trailing_Stop']) |
        (df['Position'] == -1) & (df['close'] >= df['Trailing_Stop'])
    )

    df['Exit'] = (df['Exit_TP'] | df['Exit_TS'] | df['Exit_SL']).astype(int)

    # ---------- 8️⃣ 파라미터 반환 ----------
    params = {
        'ema_len': ema_len,
        'tp': tp,
        'sl': sl,
        'atr_len': atr_len,
        'vol_factor': vol_factor,
        'max_pos': max_pos
    }
    return df, params