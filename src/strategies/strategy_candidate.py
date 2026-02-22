import pandas as pd
import numpy as np
import pandas_ta as ta

def apply_strategy(df, ema_len=30, tp=0.02, sl=0.015):
    """
    다이버전스 Reversal + 추세 방어 전략
    - Long: 과거 10캔들 내 VAL 아래로 내려간 적이 있고, 현재 캔들이 VAL 위로 상향 돌파 + CVD 골든크로스 + 추세 방어
    - Short: 과거 10캔들 내 VAH 위로 올라간 적이 있고, 현재 캔들이 VAH 아래로 하향 돌파 + CVD 데드크로스 + 추세 방어
    - 최소 거래 보장: CVD 크로스만 있으면 진입 허용 (블록 조건 무시)
    """
    # ---------- 필수 컬럼 체크 및 자동 생성 ----------
    required = ['close', 'low', 'high', 'volume', 'RSI', 'VAL', 'VAH', 'CVD', 'CVD_Signal', 'ADX', 'EMA_200']
    for col in required:
        if col not in df.columns:
            if col == 'RSI':
                df['RSI'] = ta.rsi(df['close'], length=14)
            elif col == 'EMA_200':
                df['EMA_200'] = ta.ema(df['close'], length=200)
            elif col == 'ADX':
                df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14']
            elif col == 'VAL':
                df['VAL'] = df['low'].rolling(10).min()
            elif col == 'VAH':
                df['VAH'] = df['high'].rolling(10).max()
            elif col == 'CVD':
                df['CVD'] = df['volume'].rolling(10).mean()
            elif col == 'CVD_Signal':
                df['CVD_Signal'] = ta.ema(df['CVD'], length=10)
            else:
                raise KeyError(f"필수 컬럼 '{col}'이(가) 누락되었습니다.")

    # ---------- 1. 롱(Long) 진입 로직 ----------
    # 과거 10캔들 내 VAL 아래로 내려간 적이 있는지
    df['Close_Below_VAL_10'] = df['close'].rolling(10).min() < df['VAL']
    # 현재 캔들이 VAL 위로 상향 돌파
    df['Close_Above_VAL'] = df['close'] > df['VAL']
    # CVD 골든크로스 (수급 반전)
    df['CVD_Golden'] = ta.crossover(df['CVD'], df['CVD_Signal'])
    # 기본 롱 진입 조건
    long_base = df['Close_Below_VAL_10'] & df['Close_Above_VAL'] & df['CVD_Golden']

    # ---------- 2. 숏(Short) 진입 로직 ----------
    # 과거 10캔들 내 VAH 위로 올라간 적이 있는지
    df['Close_Above_VAH_10'] = df['close'].rolling(10).max() > df['VAH']
    # 현재 캔들이 VAH 아래로 하향 돌파
    df['Close_Below_VAH'] = df['close'] < df['VAH']
    # CVD 데드크로스 (수급 반전)
    df['CVD_Dead'] = ta.crossunder(df['CVD'], df['CVD_Signal'])
    # 기본 숏 진입 조건
    short_base = df['Close_Above_VAH_10'] & df['Close_Below_VAH'] & df['CVD_Dead']

    # ---------- 3. 추세 방어 (ADX + EMA_200 거리) ----------
    # 가격 대비 EMA_200 거리 (%)
    df['Price_Dist_EMA'] = (df['close'] - df['EMA_200']) / df['EMA_200']
    # 강한 추세 + 가격 멀리 떨어짐 (2% 이상) → 진입 차단
    df['Trend_Block'] = (df['ADX'] > 25) & (abs(df['Price_Dist_EMA']) > 0.02)

    # ---------- 4. 최소 거래 보장용 보조 진입 (CVD 크로스만) ----------
    # 보조 롱: CVD 골든크로스 + 현재 가격이 VAL 위 + EMA_200 근처
    df['Fallback_Long'] = df['CVD_Golden'] & (df['close'] > df['VAL']) & (df['close'] > df['EMA_200'])
    # 보조 숏: CVD 데드크로스 + 현재 가격이 VAH 아래 + EMA_200 근처
    df['Fallback_Short'] = df['CVD_Dead'] & (df['close'] < df['VAH']) & (df['close'] < df['EMA_200'])

    # 보조 진입은 추세 방어 무시 (최소 거래 보장)
    df['Fallback_Long'] = df['Fallback_Long'] & ~df['Trend_Block']
    df['Fallback_Short'] = df['Fallback_Short'] & ~df['Trend_Block']

    # ---------- 5. 최종 진입 신호 ----------
    # 메인 신호 + 보조 신호 결합
    df['Long_Signal'] = (long_base & ~df['Trend_Block']) | df['Fallback_Long']
    df['Short_Signal'] = (short_base & ~df['Trend_Block']) | df['Fallback_Short']

    # ---------- 6. 포지션 관리 ----------
    df['Signal'] = np.where(df['Long_Signal'], 1,
                np.where(df['Short_Signal'], -1, 0))
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().shift(1).fillna(0)
    df['Entry_Flag'] = (df['Signal'] != 0) & (df['Position'] == 0)
    df['Entry_Price'] = np.where(df['Entry_Flag'], df['close'], np.nan).ffill()

    # ---------- 7. TP/SL ----------
    df['target_tp'] = tp
    df['target_sl'] = sl
    df['TP'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 + tp),
                         df['Entry_Price'] * (1 - tp))
    df['SL'] = np.where(df['Signal'] == 1, df['Entry_Price'] * (1 - sl),
                         df['Entry_Price'] * (1 + sl))

    return df, {'tp': tp, 'sl': sl}