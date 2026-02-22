import pandas_ta as ta

def apply_strategy(df, ema_len=30):
    # 1. 기본 지표 계산
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['ADX'] = ta.adx(df['high'], df['low'], df['close'], length=14)['ADX']
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['CVD'] = ta.cvd(df['high'], df['low'], df['close'], length=14)
    df['EMA_ema_len'] = ta.ema(df['close'], length=ema_len)
    df['EMA_200'] = ta.ema(df['close'], length=200)

    # 2. 구조 레벨 정의
    df['Below_Structure'] = df['close'] < df['VAL']
    df['Above_Structure'] = df['close'] > df['VAH']

    # 3. 3‑바 최저/최고
    df['Low_3'] = df['low'].rolling(3).min()
    df['High_3'] = df['high'].rolling(3).max()

    # 4. CVD 신호 (전일 대비 변화)
    df['CVD_Signal'] = df['CVD'].shift(1)

    # 5. 동적 TP/SL 계산
    last_atr = df['ATR'].iloc[-1] if 'ATR' in df.columns else 0.01
    last_close = df['close'].iloc[-1]
    d_tp = (last_atr * 2.0) / last_close
    d_sl = (last_atr * 1.5) / last_close
    tp = max(d_tp, 0.02)
    sl = max(d_sl, 0.015)

    # 6. 위험 필터링 강화
    #   - ADX > 25 (강한 추세)
    #   - EMA_200 정렬 (장기 추세와 일치 여부)
    #   - EMA_ema_len 정렬 (단기 추세와 일치 여부)
    df['Long_Signal'] = (
        df['Below_Structure'] &
        (df['low'] == df['Low_3']) &
        (df['RSI'] > df['RSI'].shift(1)) &
        (df['CVD'] > df['CVD_Signal']) &
        (df['close'] > df['EMA_ema_len']) &
        (df['ADX'] > 25) &
        (df['close'] > df['EMA_200'])
    ).fillna(False)

    df['Short_Signal'] = (
        df['Above_Structure'] &
        (df['high'] == df['High_3']) &
        (df['RSI'] < df['RSI'].shift(1)) &
        (df['CVD'] < df['CVD_Signal']) &
        (df['close'] < df['EMA_ema_len']) &
        (df['ADX'] > 25) &
        (df['close'] < df['EMA_200'])
    ).fillna(False)

    # 7. 최종 반환
    return df, {'tp': tp, 'sl': sl}