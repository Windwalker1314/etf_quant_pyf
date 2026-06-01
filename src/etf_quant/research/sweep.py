from __future__ import annotations

from dataclasses import replace
from itertools import product
from pathlib import Path
from typing import Iterable

import pandas as pd

from etf_quant.backtest.engine import BacktestEngine
from etf_quant.backtest.metrics import max_drawdown
from etf_quant.config.schema import AppConfig, StrategyConfig
from etf_quant.data.dataset import MarketData
from etf_quant.factors.library import compute_factor_panel
from etf_quant.io import ensure_dir
from etf_quant.strategies.registry import build_strategy
from etf_quant.validation.walk_forward import WalkForwardValidator


DEFAULT_POSITION_CAPS = [0.50, 0.60, 0.70, 0.80]
DEFAULT_TREND_BUCKET_CAPS = [0.50, 0.60, 0.70, 0.80]
DEFAULT_TREND_GROUP_CAPS = [0.70, 0.80, 0.90]
DEFAULT_CRISIS_WINDOWS = [
    ("2008_financial_crisis", "2007-10-09", "2009-03-09"),
    ("2011_eurozone_us_downgrade", "2011-05-02", "2011-10-03"),
    ("2015_2016_global_shock", "2015-06-12", "2016-02-11"),
    ("2018_hike_trade_tension", "2018-01-26", "2018-12-24"),
    ("2020_covid_crash", "2020-02-19", "2020-03-23"),
    ("2022_rate_hike_valuation", "2022-01-03", "2022-10-12"),
]


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


def run_position_cap_sweep(
    config: AppConfig,
    market_data: MarketData,
    output_dir: str | Path | None = None,
    caps: Iterable[float] = DEFAULT_POSITION_CAPS,
    include_walk_forward: bool = False,
) -> pd.DataFrame:
    if config.strategy.name != "bigquant_rotation":
        raise ValueError("run_position_cap_sweep only supports bigquant_rotation")

    target_dir = ensure_dir(output_dir or config.output_dir / "sweeps")
    factor_data = compute_factor_panel(market_data, config.factors)
    engine = BacktestEngine(config.backtest)
    rows: list[dict[str, object]] = []

    for idx, cap in enumerate(caps, start=1):
        cap = float(cap)
        strategy_config = StrategyConfig(
            name=config.strategy.name,
            params={**config.strategy.params, "max_position_weight": cap},
        )
        candidate = replace(config, strategy=strategy_config)
        strategy = build_strategy(strategy_config).fit(market_data)
        result = engine.run(market_data, config.factors, strategy, factor_data=factor_data)
        rows.append(
            {
                "run_id": idx,
                "mode": "backtest",
                "max_position_weight": cap,
                **result.metrics,
            }
        )

        if include_walk_forward:
            if candidate.walk_forward is None:
                raise ValueError("walk_forward config is required for --walk-forward")
            wf_result = WalkForwardValidator(candidate).run(market_data)
            rows.append(
                {
                    "run_id": idx,
                    "mode": "walk_forward",
                    "max_position_weight": cap,
                    **wf_result.metrics,
                }
            )

    frame = pd.DataFrame(rows)
    sort_cols = ["mode", "sharpe", "annualized_return", "max_drawdown", "annualized_turnover"]
    ascending = [True, False, False, False, True]
    existing = [col for col in sort_cols if col in frame.columns]
    if existing:
        frame = frame.sort_values(existing, ascending=ascending[: len(existing)]).reset_index(drop=True)
    frame.to_csv(target_dir / "position_cap_sweep.csv", index=False)
    return frame


def run_trend_state_budget_sweep(
    config: AppConfig,
    market_data: MarketData,
    output_dir: str | Path | None = None,
    bucket_caps: Iterable[float] = DEFAULT_TREND_BUCKET_CAPS,
    group_caps: Iterable[float] = DEFAULT_TREND_GROUP_CAPS,
    weak_group_caps: Iterable[float] = (0.30, 0.40, 0.50),
    include_walk_forward: bool = False,
) -> pd.DataFrame:
    if config.strategy.name != "bigquant_rotation":
        raise ValueError("run_trend_state_budget_sweep only supports bigquant_rotation")

    target_dir = ensure_dir(output_dir or config.output_dir / "sweeps")
    factor_data = compute_factor_panel(market_data, config.factors)
    engine = BacktestEngine(config.backtest)
    rows: list[dict[str, object]] = []

    for idx, (bucket_cap, group_cap, weak_group_cap) in enumerate(
        product(bucket_caps, group_caps, weak_group_caps),
        start=1,
    ):
        bucket_cap = float(bucket_cap)
        group_cap = float(group_cap)
        weak_group_cap = float(weak_group_cap)
        if bucket_cap > group_cap:
            continue
        params = {
            "use_trend_state_budget": True,
            "trend_state_budgets": {
                "strong": {"bucket_cap": bucket_cap, "group_cap": group_cap},
                "neutral": {
                    "bucket_cap": min(bucket_cap, 0.60),
                    "group_cap": min(group_cap, 0.80),
                },
                "weak": {
                    "bucket_cap": min(bucket_cap, 0.40),
                    "group_cap": weak_group_cap,
                },
            },
        }
        strategy_config = StrategyConfig(
            name=config.strategy.name,
            params={**config.strategy.params, **params},
        )
        candidate = replace(config, strategy=strategy_config)
        strategy = build_strategy(strategy_config).fit(market_data)
        result = engine.run(market_data, config.factors, strategy, factor_data=factor_data)
        rows.append(
            {
                "run_id": idx,
                "mode": "backtest",
                "strong_bucket_cap": bucket_cap,
                "strong_group_cap": group_cap,
                "weak_group_cap": weak_group_cap,
                **result.metrics,
            }
        )

        if include_walk_forward:
            if candidate.walk_forward is None:
                raise ValueError("walk_forward config is required for --walk-forward")
            wf_result = WalkForwardValidator(candidate).run(market_data)
            rows.append(
                {
                    "run_id": idx,
                    "mode": "walk_forward",
                    "strong_bucket_cap": bucket_cap,
                    "strong_group_cap": group_cap,
                    "weak_group_cap": weak_group_cap,
                    **wf_result.metrics,
                }
            )

    frame = pd.DataFrame(rows)
    sort_cols = ["mode", "sharpe", "annualized_return", "max_drawdown", "annualized_turnover"]
    ascending = [True, False, False, False, True]
    existing = [col for col in sort_cols if col in frame.columns]
    if existing:
        frame = frame.sort_values(existing, ascending=ascending[: len(existing)]).reset_index(drop=True)
    frame.to_csv(target_dir / "trend_state_budget_sweep.csv", index=False)
    frame.head(20).to_csv(target_dir / "trend_state_budget_sweep_top20.csv", index=False)
    return frame


def summarize_crisis_windows(
    equity_curve: pd.Series,
    weights: pd.DataFrame,
    turnover: pd.Series,
    windows: Iterable[tuple[str, str, str]] = DEFAULT_CRISIS_WINDOWS,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for name, start, end in windows:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        window_equity = equity_curve.loc[(equity_curve.index >= start_ts) & (equity_curve.index <= end_ts)]
        window_weights = weights.loc[(weights.index >= start_ts) & (weights.index <= end_ts)]
        window_turnover = turnover.loc[(turnover.index >= start_ts) & (turnover.index <= end_ts)]
        if window_equity.empty:
            continue

        long_weights = window_weights.clip(lower=0.0)
        avg_weights = long_weights.mean().sort_values(ascending=False)
        top_holdings = [
            f"{symbol}:{weight:.1%}"
            for symbol, weight in avg_weights[avg_weights > 1e-9].head(3).items()
        ]
        gross_exposure = long_weights.sum(axis=1)
        max_weight = long_weights.max(axis=1) if not long_weights.empty else pd.Series(dtype=float)
        rows.append(
            {
                "window": name,
                "start": start_ts.date().isoformat(),
                "end": end_ts.date().isoformat(),
                "observations": int(len(window_equity)),
                "window_return": float(window_equity.iloc[-1] / window_equity.iloc[0] - 1.0),
                "max_drawdown": max_drawdown(window_equity),
                "avg_gross_exposure": float(gross_exposure.mean()) if not gross_exposure.empty else 0.0,
                "max_single_asset_weight": float(max_weight.max()) if not max_weight.empty else 0.0,
                "trade_count": int(window_turnover.gt(1e-9).sum()),
                "top_holdings": "; ".join(top_holdings),
            }
        )
    return pd.DataFrame(rows)


def run_crisis_window_report(
    config: AppConfig,
    market_data: MarketData,
    output_dir: str | Path | None = None,
    windows: Iterable[tuple[str, str, str]] = DEFAULT_CRISIS_WINDOWS,
) -> pd.DataFrame:
    target_dir = ensure_dir(output_dir or config.output_dir / "risk_reports")
    strategy = build_strategy(config.strategy).fit(market_data)
    result = BacktestEngine(config.backtest).run(market_data, config.factors, strategy)
    frame = summarize_crisis_windows(result.equity_curve, result.weights, result.turnover, windows=windows)
    frame.to_csv(target_dir / "crisis_windows.csv", index=False)
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
