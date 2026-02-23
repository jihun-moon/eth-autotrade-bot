import numpy as np

def apply_strategy(df):
    tp = 0.015
    sl = 0.012
    
    # 진입 구역
    df['At_VAL'] = df['close'] < df['VAL'] * 1.002
    df['At_VAH'] = df['close'] > df['VAH'] * 0.998
    
    # RSI 방향
    df['RSI_up']   = df['RSI'] > df['RSI'].shift(1)
    df['RSI_down'] = df['RSI'] < df['RSI'].shift(1)
    
    # ADX 강도 필터
    df['ADX_strong'] = df['ADX'] > 20
    
    # EMA_200 추세 필터
    df['EMA_up']   = df['EMA_200'] > df['EMA_200'].shift(1)
    df['EMA_down'] = df['EMA_200'] < df['EMA_200'].shift(1)
    
    # 변동성 스퀴즈 필터
    df['Squeeze_low'] = df['Squeeze_On'] < 0.5
    
    # CVD 상대 신호
    df['CVD_up']   = df['CVD'] > df['CVD_Signal']
    df['CVD_down'] = df['CVD'] < df['CVD_Signal']
    
    # POC 근접 필터
    df['Near_POC_long']  = df['close'] < df['POC'] * 1.001
    df['Near_POC_short'] = df['close'] > df['POC'] * 0.999
    
    # 롱 시그널
    df['Long_Signal'] = (
        (df['At_VAL']) &
        (df['RSI_up']) &
        (df['ADX_strong']) &
        (df['EMA_up']) &
        (df['Squeeze_low']) &
        (df['CVD_up']) &
        (df['Near_POC_long'])
    )
    
    # 숏 시그널
    df['Short_Signal'] = (
        (df['At_VAH']) &
        (df['RSI_down']) &
        (df['ADX_strong']) &
        (df['EMA_down']) &
        (df['Squeeze_low']) &
        (df['CVD_down']) &
        (df['Near_POC_short'])
    )
    
    # 최종 시그널
    df['Signal'] = np.where(df['Long_Signal'], 1,
                           np.where(df['Short_Signal'], -1, 0))
    
    params = {'tp': tp, 'sl': sl}
    return df, params