import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Literal, Optional, Dict, Any

# ──────────────────────────────────────────────────────────────────────
#  전략 핵심 로직
# ──────────────────────────────────────────────────────────────────────
def apply_strategy(
    df: pd.DataFrame,
    *,
    ema_len: int = 30,
    atr_len: int = 14,
    tp_multiplier: float = 2.0,
    sl_multiplier: float = 1.5,
    tp_fillna_ratio: float = 0.02,   # 2% of close (ratio)
    sl_fillna_ratio: float = 0.015,  # 1.5% of close (ratio)
    tp_clip_lower: float = 0.015,    # 최소 TP 비율 (1.5%)
    sl_clip_lower: float = 0.01,     # 최소 SL 비율 (1%)
    adx_threshold: int = 25,
    cfd_signal_len: int = 10,
    cfd_signal_multiplier: float = 0.0,
    rsi_len: int = 14,
    rsi_overbought: int = 70,
    rsi_oversold: int = 30,
    risk_per_trade: float = 0.01,    # 1% of account
    initial_capital: float = 100_000,
    commission: float = 0.0001,      # 0.01% per trade
    slippage: float = 0.0001,        # 0.01% per trade
    trailing_stop_multiplier: float = 1.0,
    trailing_stop_len: int = 14,
    backtest: bool = False,
    log_level: Literal["INFO", "DEBUG", "WARN", "ERROR"] = "INFO",
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """
    ATR 기반 TP/SL, CVD·ADX·EMA·RSI·VAH/VAL 필터를 결합한 롱/숏 진입·청산 전략.
    
    Parameters
    ----------
    df : pd.DataFrame
        반드시 `['high', 'low', 'close', 'volume']` 컬럼을 포함해야 함.
    ema_len : int, default 30
        진입·청산에 사용할 EMA 기간.
    atr_len : int, default 14
        ATR 계산에 사용할 기간.
    tp_multiplier / sl_multiplier : float
        TP / SL 를 ATR 로 몇 배 적용할지.
    tp_fillna_ratio / sl_fillna_ratio : float
        ATR 값이 NaN 일 때 사용할 비율(close 대비). 기본값은 2%·1.5%.
    tp_clip_lower / sl_clip_lower : float
        TP/SL 비율이 너무 작아지는 것을 방지하기 위한 하한값.
    adx_threshold : int
        ADX 가 이 값 이하이면 “비추세” 로 간주, 진입 필터에 사용.
    cfd_signal_len / cfd_signal_multiplier : int, float
        CVD 의 이동 평균 길이와 신호 배율. 기본값은 10일 평균, 배율 0 (즉, CVD 자체 사용).
    rsi_len, rsi_overbought, rsi_oversold : int, int, int
        RSI 계산 및 과매수/과매도 임계값.
    risk_per_trade : float
        계좌 대비 위험 비율 (예: 0.01 → 1%).
    initial_capital : float
        백테스트 시 초기 자본 (단위: 원·달러 등).
    commission, slippage : float
        거래당 비용·슬리피지 비율.
    trailing_stop_multiplier : float
        트레일링 스톱을 ATR 로 몇 배 적용할지 (0이면 비활성화).
    trailing_stop_len : int
        트레일링 스톱에 사용할 ATR 기간.
    backtest : bool
        True이면 거래 로그·Equity Curve·성과 지표를 반환.
    log_level : str
        전략 실행 중 출력할 로그 레벨.
    
    Returns
    -------
    df : pd.DataFrame
        원본 df에 `target_tp`, `target_sl`, `position`, `entry_price`,
        `exit_price`, `profit`, `trade_log` 등 추가 컬럼이 포함된 DataFrame.
    result : dict
        마지막 봉의 TP/SL 비율을 담은 dict (`{'tp': last_tp, 'sl': last_sl}`).
    """
    # ──────────────────────────────────────────────────────────────────────
    #  1️⃣ 기본 지표 계산 (ATR, EMA, EMA_200, RSI, VAH/VAL, CVD, ADX)
    # ──────────────────────────────────────────────────────────────────────
    # ATR
    df["ATR"] = ta.atr(df["high"], df["low"], df["close"], length=atr_len)

    # EMA (진입·청산용)
    df["EMA"] = ta.ema(df["close"], length=ema_len)

    # EMA_200 (장기 추세 필터)
    df["EMA_200"] = ta.ema(df["close"], length=200)

    # RSI
    df["RSI"] = ta.rsi(df["close"], length=rsi_len)

    # VAH / VAL (매물대)
    df["VAH"] = ta.vah(df["high"], df["low"], df["close"])
    df["VAL"] = ta.val(df["high"], df["low"], df["close"])

    # CVD (Cumulative Volume Delta)
    df["CVD"] = ta.cvd(df["high"], df["low"], df["close"], df["volume"])

    # ADX (추세 강도)
    df["ADX"] = ta.adx(df["high"], df["low"], df["close"], length=14)

    # ──────────────────────────────────────────────────────────────────────
    #  2️⃣ TP / SL (ATR 기반 절대값) 계산
    # ──────────────────────────────────────────────────────────────────────
    # TP = close + ATR * multiplier
    df["target_tp"] = df["close"] + df["ATR"] * tp_multiplier
    # SL = close - ATR * multiplier
    df["target_sl"] = df["close"] - df["ATR"] * sl_multiplier

    # NaN 처리 (ATR 가 NaN이면 비율 기반 fallback)
    if df["ATR"].isna().any():
        # 비율 fallback: 2%·1.5% of close
        df["target_tp"] = df["target_tp"].fillna(df["close"] * tp_fillna_ratio)
        df["target_sl"] = df["target_sl"].fillna(df["close"] * sl_fillna_ratio)

    # 최소 비율 제한 (TP/SL 가 너무 작아지는 경우 방지)
    df["target_tp"] = df["target_tp"].clip(lower=df["close"] * tp_clip_lower)
    df["target_sl"] = df["target_sl"].clip(lower=df["close"] * sl_clip_lower)

    # ──────────────────────────────────────────────────────────────────────
    #  3️⃣ CVD 신호 (이동 평균) – CVD_Signal 컬럼 생성
    # ──────────────────────────────────────────────────────────────────────
    df["CVD_Signal"] = df["CVD"].rolling(cfd_signal_len).mean()
    # CVD_Signal 은 기본값이 0이므로 별도 NaN 처리 필요 없음

    # ──────────────────────────────────────────────────────────────────────
    #  4️⃣ 진입·청산 시그널 로직
    # ──────────────────────────────────────────────────────────────────────
    # 4‑1) 롱 시그널
    df["Below_Structure"] = df["close"] < df["VAL"]
    df["Low_3"] = df["low"].rolling(3).min()
    df["Bull_Div"] = (df["low"] == df["Low_3"]) & (df["RSI"] > df["RSI"].shift(1))

    df["Long_Signal"] = (
        df["Below_Structure"]
        & df["Bull_Div"]
        & (df["CVD"] > df["CVD_Signal"])
        & (df["close"] > df["EMA"])
    )
    # ADX 가 25 이하(비추세) 혹은 장기 EMA_200 위에 있을 때 진입 허용
    df["Long_Signal"] = df["Long_Signal"] & ((df["ADX"] <= adx_threshold) | (df["close"] >= df["EMA_200"]))

    # 4‑2) 숏 시그널
    df["Above_Structure"] = df["close"] > df["VAH"]
    df["High_3"] = df["high"].rolling(3).max()
    df["Bear_Div"] = (df["high"] == df["High_3"]) & (df["RSI"] < df["RSI"].shift(1))

    df["Short_Signal"] = (
        df["Above_Structure"]
        & df["Bear_Div"]
        & (df["CVD"] < df["CVD_Signal"])
        & (df["close"] < df["EMA"])
    )
    df["Short_Signal"] = df["Short_Signal"] & ((df["ADX"] <= adx_threshold) | (df["close"] <= df["EMA_200"]))

    # ──────────────────────────────────────────────────────────────────────
    #  5️⃣ 포지션 관리 (롱/숏) – 백테스트용 로직
    # ──────────────────────────────────────────────────────────────────────
    # 초기 포지션 컬럼
    df["position"] = 0.0   # 0 = flat, 1 = long, -1 = short
    df["entry_price"] = np.nan
    df["exit_price"] = np.nan
    df["profit"] = np.nan
    df["trade_log"] = []   # 리스트 형태 (각 원소: dict)

    # 백테스트용 변수
    if backtest:
        # 초기 자본, 현재 자본, 포지션 사이즈, 트레일링 스톱 등
        capital = initial_capital
        position_size = 0.0
        trailing_stop = np.nan
        # 로그 레벨에 따라 콘솔 출력
        if log_level == "DEBUG":
            print("[DEBUG] 백테스트 시작 – 초기 자본:", capital)

    # ──────────────────────────────────────────────────────────────────────
    #  6️⃣ 시그널에 따라 포지션 진입·청산
    # ──────────────────────────────────────────────────────────────────────
    for i in range(1, len(df)):
        # 현재 시그널
        long_sig = df.loc[i, "Long_Signal"]
        short_sig = df.loc[i, "Short_Signal"]

        # 현재 포지션 상태
        cur_pos = df.loc[i, "position"]
        cur_entry = df.loc[i, "entry_price"]
        cur_exit = df.loc[i, "exit_price"]

        # ── 롱 진입 로직 ────────────────────────────────────────
        if long_sig and cur_pos == 0:
            # 위험 기반 포지션 사이즈 계산
            if backtest:
                # 현재 ATR 로 위험 금액 산정
                risk_amount = capital * risk_per_trade
                # SL 가격 = target_sl (절대값)
                sl_price = df.loc[i, "target_sl"]
                # 포지션 사이즈 = 위험 금액 / (entry_price - sl_price)
                pos_size = risk_amount / (df.loc[i, "close"] - sl_price)
                # 슬리피지·커미션 반영
                entry_price = df.loc[i, "close"] * (1 + slippage) - commission
                # 트레일링 스톱 적용 여부
                if trailing_stop_multiplier > 0:
                    trailing_stop = entry_price - df.loc[i, "ATR"] * trailing_stop_multiplier
                else:
                    trailing_stop = np.nan
                # 포지션 기록
                df.loc[i, "position"] = 1.0
                df.loc[i, "entry_price"] = entry_price
                df.loc[i, "exit_price"] = np.nan
                df.loc[i, "profit"] = np.nan
                df.loc[i, "trade_log"].append({
                    "entry_idx": i,
                    "entry_price": entry_price,
                    "sl_price": sl_price,
                    "trailing_stop": trailing_stop,
                })
                if log_level == "INFO":
                    print(f"[INFO] 롱 진입 @ {entry_price:.2f} (SL={sl_price:.2f})")
                if log_level == "DEBUG":
                    print(f"[DEBUG] 롱 진입 idx={i}, entry={entry_price:.2f}, SL={sl_price:.2f}")

        # ── 숏 진입 로직 ────────────────────────────────────────
        elif short_sig and cur_pos == 0:
            if backtest:
                risk_amount = capital * risk_per_trade
                sl_price = df.loc[i, "target_sl"]  # 숏은 SL = target_sl (절대값)
                pos_size = risk_amount / (df.loc[i, "close"] - sl_price)
                entry_price = df.loc[i, "close"] * (1 - slippage) + commission
                if trailing_stop_multiplier > 0:
                    trailing_stop = entry_price + df.loc[i, "ATR"] * trailing_stop_multiplier
                else:
                    trailing_stop = np.nan
                df.loc[i, "position"] = -1.0
                df.loc[i, "entry_price"] = entry_price
                df.loc[i, "exit_price"] = np.nan
                df.loc[i, "profit"] = np.nan
                df.loc[i, "trade_log"].append({
                    "entry_idx": i,
                    "entry_price": entry_price,
                    "sl_price": sl_price,
                    "trailing_stop": trailing_stop,
                })
                if log_level == "INFO":
                    print(f"[INFO] 숏 진입 @ {entry_price:.2f} (SL={sl_price:.2f})")
                if log_level == "DEBUG":
                    print(f"[DEBUG] 숏 진입 idx={i}, entry={entry_price:.2f}, SL={sl_price:.2f}")

        # ── 포지션 청산 로직 ────────────────────────────────────────
        # 1) TP 도달
        if cur_pos == 1 and df.loc[i, "close"] >= df.loc[i, "target_tp"]:
            exit_price = df.loc[i, "target_tp"]
            df.loc[i, "exit_price"] = exit_price
            df.loc[i, "profit"] = (exit_price - cur_entry) * pos_size
            df.loc[i, "position"] = 0.0
            if backtest:
                capital += df.loc[i, "profit"]
                if log_level == "INFO":
                    print(f"[INFO] 롱 TP 청산 @ {exit_price:.2f} (PnL={df.loc[i, 'profit']:.2f})")
                if log_level == "DEBUG":
                    print(f"[DEBUG] 롱 TP 청산 idx={i}, exit={exit_price:.2f}, PnL={df.loc[i, 'profit']:.2f}")

        # 2) SL 도달
        elif cur_pos == 1 and df.loc[i, "close"] <= df.loc[i, "target_sl"]:
            exit_price = df.loc[i, "target_sl"]
            df.loc[i, "exit_price"] = exit_price
            df.loc[i, "profit"] = (exit_price - cur_entry) * pos_size
            df.loc[i, "position"] = 0.0
            if backtest:
                capital += df.loc[i, "profit"]
                if log_level == "INFO":
                    print(f"[INFO] 롱 SL 청산 @ {exit_price:.2f} (PnL={df.loc[i, 'profit']:.2f})")
                if log_level == "DEBUG":
                    print(f"[DEBUG] 롱 SL 청산 idx={i}, exit={exit_price:.2f}, PnL={df.loc[i, 'profit']:.2f}")

        # 3) 트레일링 스톱 도달 (롱)
        elif cur_pos == 1 and trailing_stop_multiplier > 0 and df.loc[i, "close"] <= trailing_stop:
            exit_price = trailing_stop
            df.loc[i, "exit_price"] = exit_price
            df.loc[i, "profit"] = (exit_price - cur_entry) * pos_size
            df.loc[i, "position"] = 0.0
            if backtest:
                capital += df.loc[i, "profit"]
                if log_level == "INFO":
                    print(f"[INFO] 롱 트레일링 스톱 청산 @ {exit_price:.2f} (PnL={df.loc[i, 'profit']:.2f})")
                if log_level == "DEBUG":
                    print(f"[DEBUG] 롱 트레일링 스톱 청산 idx={i}, exit={exit_price:.2f}, PnL={df.loc[i, 'profit']:.2f}")

        # 4) 숏 포지션 청산 (TP, SL, 트레일링)
        elif cur_pos == -1 and df.loc[i, "close"] <= df.loc[i, "target_tp"]:
            exit_price = df.loc[i, "target_tp"]
            df.loc[i, "exit_price"] = exit_price
            df.loc[i, "profit"] = (cur_entry - exit_price) * pos_size
            df.loc[i, "position"] = 0.0
            if backtest:
                capital += df.loc[i, "profit"]
                if log_level == "INFO":
                    print(f"[INFO] 숏 TP 청산 @ {exit_price:.2f} (PnL={df.loc[i, 'profit']:.2f})")
                if log_level == "DEBUG":
                    print(f"[DEBUG] 숏 TP 청산 idx={i}, exit={exit_price:.2f}, PnL={df.loc[i, 'profit']:.2f}")

        elif cur_pos == -1 and df.loc[i, "close"] >= df.loc[i, "target_sl"]:
            exit_price = df.loc[i, "target_sl"]
            df.loc[i, "exit_price"] = exit_price
            df.loc[i, "profit"] = (cur_entry - exit_price) * pos_size
            df.loc[i, "position"] = 0.0
            if backtest:
                capital += df.loc[i, "profit"]
                if log_level == "INFO":
                    print(f"[INFO] 숏 SL 청산 @ {exit_price:.2f} (PnL={df.loc[i, 'profit']:.2f})")
                if log_level == "DEBUG":
                    print(f"[DEBUG] 숏 SL 청산 idx={i}, exit={exit_price:.2f}, PnL={df.loc[i, 'profit']:.2f}")

        elif cur_pos == -1 and trailing_stop_multiplier > 0 and df.loc[i, "close"] >= trailing_stop:
            exit_price = trailing_stop
            df.loc[i, "exit_price"] = exit_price
            df.loc[i, "profit"] = (cur_entry - exit_price) * pos_size
            df.loc[i, "position"] = 0.0
            if backtest:
                capital += df.loc[i, "profit"]
                if log_level == "INFO":
                    print(f"[INFO] 숏 트레일링 스톱 청산 @ {exit_price:.2f} (PnL={df.loc[i, 'profit']:.2f})")
                if log_level == "DEBUG":
                    print(f"[DEBUG] 숏 트레일링 스톱 청산 idx={i}, exit={exit_price:.2f}, PnL={df.loc[i, 'profit']:.2f}")

        # 포지션이 이미 있으면 시그널이 반대일 경우 청산 (예: 롱 → 숏 전환)
        elif cur_pos == 1 and short_sig:
            # 롱 포지션 청산 후 숏 진입 (즉시 전환)
            # ① 롱 청산
            exit_price = df.loc[i, "target_sl"]  # 기본 SL 사용
            df.loc[i, "exit_price"] = exit_price
            df.loc[i, "profit"] = (exit_price - cur_entry) * pos_size
            df.loc[i, "position"] = 0.0
            if backtest:
                capital += df.loc[i, "profit"]
                if log_level == "INFO":
                    print(f"[INFO] 롱 → 숏 전환 (청산) @ {exit_price:.2f} (PnL={df.loc[i, 'profit']:.2f})")
                if log_level == "DEBUG":
                    print(f"[DEBUG] 롱 → 숏 전환 idx={i}, exit={exit_price:.2f}, PnL={df.loc[i, 'profit']:.2f}")

            # ② 숏 진입 (위에서 정의한 숏 진입 로직 재사용)
            # (위 루프 안에서 이미 숏 진입 로직이 실행되므로 여기서는 별도 처리 안 함)

        elif cur_pos == -1 and long_sig:
            # 숏 → 롱 전환 (청산 후 롱 진입)
            exit_price = df.loc[i, "target_sl"]
            df.loc[i, "exit_price"] = exit_price
            df.loc[i, "profit"] = (cur_entry - exit_price) * pos_size
            df.loc[i, "position"] = 0.0
            if backtest:
                capital += df.loc[i, "profit"]
                if log_level == "INFO":
                    print(f"[INFO] 숏 → 롱 전환 (청산) @ {exit_price:.2f} (PnL={df.loc[i, 'profit']:.2f})")
                if log_level == "DEBUG":
                    print(f"[DEBUG] 숏 → 롱 전환 idx={i}, exit={exit_price:.2f}, PnL={df.loc[i, 'profit']:.2f}")

    # ──────────────────────────────────────────────────────────────────────
    #  7️⃣ 백테스트 성과 지표 계산 (옵션)
    # ──────────────────────────────────────────────────────────────────────
    if backtest:
        # 총수익, Max‑DD, Sharpe, Profit‑Factor 등
        total_return = (capital - initial_capital) / initial_capital
        equity_curve = pd.DataFrame({"idx": df.index, "equity": capital})
        # 성과 지표
        profit_factor = np.sum(df["profit"] > 0) / np.sum(df["profit"] < 0) if np.sum(df["profit"] < 0) != 0 else np.inf
        win_rate = np.sum(df["profit"] > 0) / len(df[df["position"] != 0])
        avg_trade = np.mean(df["profit"])
        expectancy = np.mean(df["profit"] * df["position"])

        performance = {
            "total_return": total_return,
            "max_drawdown": equity_curve["equity"].cummax() - equity_curve["equity"],
            "sharpe_ratio": np.sqrt(252) * np.mean(df["profit"] / equity_curve["equity"].shift(1)) / np.std(df["profit"] / equity_curve["equity"].shift(1)),
            "profit_factor": profit_factor,
            "win_rate": win_rate,
            "avg_trade": avg_trade,
            "expectancy": expectancy,
            "trade_count": len(df[df["position"] != 0]),
        }

        # 로그 출력 (INFO 레벨)
        if log_level == "INFO":
            print("[INFO] 백테스트 결과")
            for k, v in performance.items():
                print(f"  {k:>20}: {v:.4f}")

        # 반환값에 성과 지표 포함
        result = {"tp": df["target_tp"].iloc[-1], "sl": df["target_sl"].iloc[-1], **performance}
    else:
        result = {"tp": df["target_tp"].iloc[-1], "sl": df["target_sl"].iloc[-1]}

    return df, result