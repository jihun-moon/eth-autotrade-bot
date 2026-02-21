import vectorbt as vbt

def run_vectorbt_backtest(df):
    # 시그널 추출
    entries = df['Long_Signal']
    
    # TP/SL 설정 (피보나치 1.0 비율 가정)
    # 실제 환경에서는 개별 진입가 기준이나, 벡터 연산에서는 고정 비율로 우선 테스트
    portfolio = vbt.Portfolio.from_signals(
        df['close'], 
        entries, 
        None, 
        fees=0.001,      # 수수료 0.1%
        slippage=0.0005, # 슬리피지 0.05%
        freq='3m'
    )
    
    print(portfolio.stats())
    portfolio.plot().write_image("backtest_result.png") # 결과 차트 저장