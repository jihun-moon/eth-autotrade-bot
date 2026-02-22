import pandas_ta as ta
import pandas as pd

def apply_strategy(
    df: pd.DataFrame,
    ema_len: int = 30,
    adx_len: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    bb_len: int = 20,
    bb_std: int = 2,
    rsi_len: int = 14,
    cci_len: int = 20,
    val_len: int = 20,
    vah_len: int = 20,
    atr_len: int = 14,
) -> tuple[pd.DataFrame, dict]:
    """
    개선된 매매 전략 적용 함수

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV 데이터프레임 (컬럼: ['open','high','low','close','volume'] 등)
    ema_len, adx_len, macd_fast, macd_slow, macd_signal, bb_len, bb_std,
    rsi_len, cci_len, val_len, vah_len, atr_len : int
        각 지표의 파라미터 (기본값은 일반적인 트레이딩 설정)

    Returns
    -------
    tuple
        (df, {'tp': 0.02, 'sl': 0.015})
        - df : 원본 데이터에 모든 보조 지표가 추가된 DataFrame
        - dict : 고정 TP/SL 설정값 (요청대로 반드시 0.02 / 0.015)
    """

    # ------------------------------------------------------------------
    # 1️⃣  보조 지표 계산 (누락된 컬럼이 있으면 자동 생성)
    # ------------------------------------------------------------------
    # ① 구조 레벨 (VAL / VAH)
    df['VAL'] = df['high'].rolling(val_len).max()
    df['VAH'] = df['low'].rolling(vah_len).min()

    # ② ATR (리스크 관리용)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=atr_len)

    # ③ EMA (단기 추세)
    df['EMA'] = ta.ema(df['close'], length=ema_len)

    # ④ EMA‑200 (장기 추세)
    df['EMA_200'] = ta.ema(df['close'], length=200)

    # ⑤ RSI
    df['RSI'] = ta.rsi(df['close'], length=rsi_len)

    # ⑥ Commodity Channel Index (CVD)
    df['CVD'] = ta.commodity_channel_index(df['high'], df['low'], df['close'], length=cci_len)

    # ⑦ CVD EMA (신호선)
    df['CVD_Signal'] = ta.ema(df['CVD'], length=ema_len)

    # ⑧ ADX (추세 강도)
    df['ADX'] = ta.adx(df['high'], df['low'], df['close'], length=adx_len)

    # ⑨ MACD & 히스토그램
    macd = ta.macd(df['close'], fast=macd_fast, slow=macd_slow, signal=macd_signal)
    df['MACD'] = macd['MACD']
    df['MACD_hist'] = macd['MACD_hist']

    # ⑩ Bollinger Bands (볼린저밴드)
    bb = ta.bbands(df['close'], length=bb_len, std=bb_std)
    df['BB_upper'] = bb['BB_upper']
    df['BB_lower'] = bb['BB_lower']

    # ⑪ 3‑period 저점 / 고점 (다이버전스 검출용)
    df['Low_3'] = df['low'].rolling(3).min()
    df['High_3'] = df['high'].rolling(3).max()

    # ------------------------------------------------------------------
    # 2️⃣  다이버전스 로직 (Bull / Bear)
    # ------------------------------------------------------------------
    df['Bull_Div'] = (df['low'] == df['Low_3']) & (df['RSI'] > df['RSI'].shift(1))
    df['Bear_Div'] = (df['high'] == df['High_3']) & (df['RSI'] < df['RSI'].shift(1))

    # ------------------------------------------------------------------
    # 3️⃣  롱 / 숏 시그널 정의
    # ------------------------------------------------------------------
    # ① 롱 시그널
    df['Long_Signal'] = (
        (df['close'] < df['VAL'])                     # 구조 레벨 아래
        & df['Bull_Div']                              # RSI 다이버전스
        & (df['CVD'] > df['CVD_Signal'])              # CVD 상승 신호
        & (df['close'] > df['EMA'])                    # EMA 상승
        & (df['MACD_hist'] > 0)                        # MACD 히스토그램 양수
        & (df['close'] > df['BB_upper'])               # 볼린저밴드 상단 돌파
        & (df['ADX'] > 25)                            # ADX 추세 강도
        & (df['close'] > df['EMA_200'])                # 장기 EMA‑200 위
    ).fillna(False)

    # ② 숏 시그널
    df['Short_Signal'] = (
        (df['close'] > df['VAH'])                     # 구조 레벨 위
        & df['Bear_Div']                              # RSI 다이버전스
        & (df['CVD'] < df['CVD_Signal'])              # CVD 하락 신호
        & (df['close'] < df['EMA'])                    # EMA 하락
        & (df['MACD_hist'] < 0)                        # MACD 히스토그램 음수
        & (df['close'] < df['BB_lower'])               # 볼린저밴드 하단 돌파
        & (df['ADX'] > 25)                            # ADX 추세 강도
        & (df['close'] < df['EMA_200'])                # 장기 EMA‑200 아래
    ).fillna(False)

    # ------------------------------------------------------------------
    # 4️⃣  동적 TP / SL (ATR 기반) → 최종 반환값은 고정값으로 오버라이드
    # ------------------------------------------------------------------
    # 마지막 ATR와 종가 확보 (ATR 컬럼이 없을 경우 기본값 사용)
    last_atr = df['ATR'].iloc[-1] if 'ATR' in df.columns else 0.01
    last_close = df['close'].iloc[-1]

    # 동적 TP/SL 계산 (예시)
    d_tp = (last_atr * 2.0) / last_close
    d_sl = (last_atr * 1.5) / last_close

    # (필요 시) 동적 TP/SL을 DataFrame에 저장해 두면 추후 활용 가능
    df['TP_dynamic'] = d_tp
    df['SL_dynamic'] = d_sl

    # ------------------------------------------------------------------
    # 5️⃣  최종 반환 (요청대로 고정 TP/SL)
    # ------------------------------------------------------------------
    return df, {'tp': 0.02, 'sl': 0.015}