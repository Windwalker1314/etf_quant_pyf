from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from etf_quant.backtest.engine import BacktestEngine
from etf_quant.backtest.metrics import summarize_performance
from etf_quant.config.schema import AppConfig
from etf_quant.data.dataset import MarketData
from etf_quant.strategies.registry import build_strategy
from etf_quant.validation.windows import Window, make_walk_forward_windows


@dataclass(frozen=True)
class WalkForwardResult:
    equity_curve: pd.Series
    fold_metrics: pd.DataFrame
    windows: list[Window]
    metrics: dict[str, float]


class WalkForwardValidator:
    def __init__(self, config: AppConfig):
        if config.walk_forward is None:
            raise ValueError("walk_forward config is required")
        self.config = config

    def run(self, market_data: MarketData) -> WalkForwardResult:
        wf = self.config.walk_forward
        dates = market_data.close_wide().index
        windows = make_walk_forward_windows(
            dates.min(),
            dates.max(),
            wf.train_months,
            wf.validation_months,
            wf.test_months,
            wf.step_months,
            wf.mode,
        )
        fold_equities = []
        fold_metrics = []
        engine = BacktestEngine(self.config.backtest)
        capital = self.config.backtest.initial_cash

        for fold_id, window in enumerate(windows, start=1):
            train = market_data.slice(window.train_start, window.train_end)
            validation = market_data.slice(window.validation_start, window.validation_end)
            test_context = market_data.slice(window.train_start, window.test_end)
            strategy = build_strategy(self.config.strategy).fit(train, validation)
            result = engine.run(test_context, self.config.factors, strategy)
            test_equity = result.equity_curve.loc[
                (result.equity_curve.index >= window.test_start)
                & (result.equity_curve.index <= window.test_end)
            ]
            if test_equity.empty:
                continue
            normalized = test_equity / test_equity.iloc[0] * capital
            capital = float(normalized.iloc[-1])
            fold_equities.append(normalized)
            fold_metrics.append(
                {
                    "fold": fold_id,
                    "train_start": window.train_start.date().isoformat(),
                    "train_end": window.train_end.date().isoformat(),
                    "validation_start": window.validation_start.date().isoformat(),
                    "validation_end": window.validation_end.date().isoformat(),
                    "test_start": window.test_start.date().isoformat(),
                    "test_end": window.test_end.date().isoformat(),
                    **summarize_performance(normalized),
                }
            )

        if not fold_equities:
            raise ValueError("No walk-forward folds produced equity data")
        equity = pd.concat(fold_equities).sort_index()
        return WalkForwardResult(
            equity_curve=equity.rename("equity"),
            fold_metrics=pd.DataFrame(fold_metrics),
            windows=windows,
            metrics=summarize_performance(equity),
        )
