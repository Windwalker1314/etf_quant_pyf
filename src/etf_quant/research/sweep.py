from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Iterable

import pandas as pd

from etf_quant.backtest.engine import BacktestEngine
from etf_quant.config.schema import AppConfig, StrategyConfig
from etf_quant.data.dataset import MarketData
from etf_quant.factors.library import compute_factor_panel
from etf_quant.io import ensure_dir
from etf_quant.strategies.registry import build_strategy


def _iter_turnover_controls() -> Iterable[dict[str, object]]:
    change_thresholds = [0.08, 0.10, 0.12, 0.15]
    score_windows = [3, 5]
    min_hold_days = [0, 2, 3]
    entry_modes = [
        {"entry_confirm_days": 1, "entry_rank_buffer": 0},
        {"entry_confirm_days": 2, "entry_rank_buffer": 0},
        {"entry_confirm_days": 2, "entry_rank_buffer": 1},
        {"entry_confirm_days": 3, "entry_rank_buffer": 1},
    ]
    for change_threshold, score_window, min_hold, entry_mode in product(
        change_thresholds, score_windows, min_hold_days, entry_modes
    ):
        yield {
            "change_threshold": change_threshold,
            "score_smoothing_window": score_window,
            "min_hold_days": min_hold,
            **entry_mode,
        }


def _iter_gap_controls() -> Iterable[dict[str, object]]:
    change_thresholds = [0.10, 0.12, 0.15, 0.18]
    score_windows = [2, 3, 4, 5]
    gap_coefs = [0.25, 0.35, 0.45]
    gap_floors = [0.08, 0.10, 0.12]
    take_profits = [None, 0.40]
    for change_threshold, score_window, gap_coef, gap_floor, take_profit in product(
        change_thresholds, score_windows, gap_coefs, gap_floors, take_profits
    ):
        yield {
            "change_threshold": change_threshold,
            "score_smoothing_window": score_window,
            "gap_coef": gap_coef,
            "gap_floor": gap_floor,
            "min_hold_days": 0,
            "entry_confirm_days": 1,
            "entry_rank_buffer": 0,
            "take_profit_pct": take_profit,
        }


def run_bigquant_turnover_sweep(
    config: AppConfig,
    market_data: MarketData,
    output_dir: str | Path | None = None,
    preset: str = "turnover",
) -> pd.DataFrame:
    if config.strategy.name != "bigquant_rotation":
        raise ValueError("run_bigquant_turnover_sweep only supports bigquant_rotation")

    target_dir = ensure_dir(output_dir or config.output_dir / "sweeps")
    factor_data = compute_factor_panel(market_data, config.factors)
    engine = BacktestEngine(config.backtest)
    rows: list[dict[str, object]] = []

    if preset == "turnover":
        param_iter = _iter_turnover_controls()
    elif preset == "gap":
        param_iter = _iter_gap_controls()
    else:
        raise ValueError(f"Unknown sweep preset: {preset}")

    for idx, params in enumerate(param_iter, start=1):
        strategy_config = StrategyConfig(
            name=config.strategy.name,
            params={**config.strategy.params, **params},
        )
        strategy = build_strategy(strategy_config).fit(market_data)
        result = engine.run(market_data, config.factors, strategy, factor_data=factor_data)
        row = {
            "run_id": idx,
            **params,
            **result.metrics,
        }
        rows.append(row)

    frame = pd.DataFrame(rows)
    sort_cols = ["sharpe", "annualized_return", "max_drawdown", "annualized_turnover"]
    ascending = [False, False, False, True]
    existing = [col for col in sort_cols if col in frame.columns]
    if existing:
        frame = frame.sort_values(existing, ascending=ascending[: len(existing)]).reset_index(drop=True)
    frame.to_csv(target_dir / f"bigquant_{preset}_sweep.csv", index=False)
    frame.head(20).to_csv(target_dir / f"bigquant_{preset}_sweep_top20.csv", index=False)
    return frame


def _iter_macro_risk_controls() -> Iterable[dict[str, object]]:
    breadth_thresholds = [0.45, 0.50, 0.55, 0.60]
    risk_score_thresholds = [-0.02, 0.0, 0.03]
    crash_thresholds = [-0.12, -0.08, -0.04]
    cash_weights = [0.0, 0.25, 0.50]
    defensive_hold_nums = [1, 2]
    for breadth, risk_score, crash_threshold, cash_weight, defensive_hold_num in product(
        breadth_thresholds,
        risk_score_thresholds,
        crash_thresholds,
        cash_weights,
        defensive_hold_nums,
    ):
        yield {
            "breadth_threshold": breadth,
            "risk_score_threshold": risk_score,
            "crash_momentum_threshold": crash_threshold,
            "cash_weight_when_defensive": cash_weight,
            "defensive_hold_num": defensive_hold_num,
        }


def _iter_macro_filter_controls() -> Iterable[dict[str, object]]:
    base = {
        "breadth_threshold": 0.55,
        "risk_score_threshold": 0.03,
        "crash_momentum_threshold": -0.04,
        "cash_weight_when_defensive": 0.25,
        "defensive_hold_num": 2,
        "use_macro_filter": True,
    }
    credit_spreads = [None, 5.0, 6.0, 7.0]
    credit_changes = [None, 0.75, 1.25, 1.75]
    financial_conditions = [None, -0.25, 0.0, 0.25]
    yield_curves = [None, -0.75, -0.50, -0.25]
    for credit_spread, credit_change, financial_condition, yield_curve in product(
        credit_spreads,
        credit_changes,
        financial_conditions,
        yield_curves,
    ):
        if credit_spread is None and credit_change is None and financial_condition is None and yield_curve is None:
            continue
        yield {
            **base,
            "max_credit_spread": credit_spread,
            "max_credit_spread_change_63d": credit_change,
            "max_financial_conditions": financial_condition,
            "min_yield_curve": yield_curve,
        }


def _iter_macro_trend_controls() -> Iterable[dict[str, object]]:
    base = {
        "breadth_threshold": 0.55,
        "risk_score_threshold": 0.03,
        "crash_momentum_threshold": -0.04,
        "cash_weight_when_defensive": 0.25,
        "defensive_hold_num": 2,
        "use_macro_filter": True,
        "macro_trend_col": "credit_risk_ratio",
    }
    ma_windows = [63, 126, 252]
    gaps = [None, -0.04, -0.03, -0.02, -0.01, 0.0]
    momentums = [None, -0.08, -0.06, -0.04, -0.02, 0.0]
    for ma_window, gap, momentum in product(ma_windows, gaps, momentums):
        if gap is None and momentum is None:
            continue
        yield {
            **base,
            "macro_trend_ma_window": ma_window,
            "macro_trend_min_gap": gap,
            "macro_trend_min_momentum_63d": momentum,
        }


def run_macro_risk_sweep(
    config: AppConfig,
    market_data: MarketData,
    output_dir: str | Path | None = None,
) -> pd.DataFrame:
    target_dir = ensure_dir(output_dir or config.output_dir / "sweeps")
    engine = BacktestEngine(config.backtest)
    rows: list[dict[str, object]] = []

    for idx, params in enumerate(_iter_macro_risk_controls(), start=1):
        strategy_config = StrategyConfig(
            name="macro_risk_rotation",
            params={**config.strategy.params, **params},
        )
        strategy = build_strategy(strategy_config).fit(market_data)
        result = engine.run(market_data, config.factors, strategy, factor_data={})
        rows.append(
            {
                "run_id": idx,
                **params,
                **result.metrics,
            }
        )

    frame = pd.DataFrame(rows)
    sort_cols = ["sharpe", "max_drawdown", "annualized_return", "annualized_turnover"]
    ascending = [False, False, False, True]
    frame = frame.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)
    frame.to_csv(target_dir / "macro_risk_sweep.csv", index=False)
    frame.head(20).to_csv(target_dir / "macro_risk_sweep_top20.csv", index=False)
    return frame


def run_macro_filter_sweep(
    config: AppConfig,
    market_data: MarketData,
    output_dir: str | Path | None = None,
) -> pd.DataFrame:
    target_dir = ensure_dir(output_dir or config.output_dir / "sweeps")
    engine = BacktestEngine(config.backtest)
    rows: list[dict[str, object]] = []

    for idx, params in enumerate(_iter_macro_filter_controls(), start=1):
        strategy_config = StrategyConfig(
            name="macro_risk_rotation",
            params={**config.strategy.params, **params},
        )
        strategy = build_strategy(strategy_config).fit(market_data)
        result = engine.run(market_data, config.factors, strategy, factor_data={})
        rows.append(
            {
                "run_id": idx,
                **params,
                **result.metrics,
            }
        )

    frame = pd.DataFrame(rows)
    sort_cols = ["sharpe", "max_drawdown", "annualized_return", "annualized_turnover"]
    ascending = [False, False, False, True]
    frame = frame.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)
    frame.to_csv(target_dir / "macro_filter_sweep.csv", index=False)
    frame.head(20).to_csv(target_dir / "macro_filter_sweep_top20.csv", index=False)
    return frame


def run_macro_trend_sweep(
    config: AppConfig,
    market_data: MarketData,
    output_dir: str | Path | None = None,
) -> pd.DataFrame:
    target_dir = ensure_dir(output_dir or config.output_dir / "sweeps")
    engine = BacktestEngine(config.backtest)
    rows: list[dict[str, object]] = []

    for idx, params in enumerate(_iter_macro_trend_controls(), start=1):
        strategy_config = StrategyConfig(
            name="macro_risk_rotation",
            params={**config.strategy.params, **params},
        )
        strategy = build_strategy(strategy_config).fit(market_data)
        result = engine.run(market_data, config.factors, strategy, factor_data={})
        rows.append(
            {
                "run_id": idx,
                **params,
                **result.metrics,
            }
        )

    frame = pd.DataFrame(rows)
    sort_cols = ["sharpe", "max_drawdown", "annualized_return", "annualized_turnover"]
    ascending = [False, False, False, True]
    frame = frame.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)
    frame.to_csv(target_dir / "macro_trend_sweep.csv", index=False)
    frame.head(20).to_csv(target_dir / "macro_trend_sweep_top20.csv", index=False)
    return frame
