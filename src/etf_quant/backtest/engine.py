from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from etf_quant.backtest.metrics import summarize_performance
from etf_quant.config.schema import BacktestConfig
from etf_quant.data.dataset import MarketData
from etf_quant.factors.library import compute_factor_panel
from etf_quant.strategies.base import Strategy


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.Series
    daily_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    metrics: dict[str, float]


def _rebalance_dates(dates: pd.DatetimeIndex, frequency: str) -> pd.DatetimeIndex:
    if frequency.upper() in {"D", "DAILY"}:
        return dates
    markers = pd.Series(dates, index=dates)
    return pd.DatetimeIndex(markers.groupby(markers.dt.to_period(frequency)).tail(1).values)


class BacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config

    def run(self, market_data: MarketData, factor_configs, strategy: Strategy) -> BacktestResult:
        factor_data = compute_factor_panel(market_data, factor_configs)
        close = market_data.close_wide()
        returns = close.pct_change().fillna(0.0)
        dates = close.index
        rebal_dates = set(_rebalance_dates(dates, self.config.rebalance))
        weights = pd.DataFrame(0.0, index=dates, columns=close.columns)

        current_weights = pd.Series(0.0, index=close.columns)
        for date in dates:
            if date in rebal_dates:
                visible_data = market_data.slice(end=date)
                visible_factors = {
                    factor_name: values.loc[:date] for factor_name, values in factor_data.items()
                }
                current_weights = strategy.generate_weights(date, visible_data, visible_factors)
                current_weights = current_weights.reindex(close.columns).fillna(0.0)
            weights.loc[date] = current_weights

        effective_weights = weights.shift(1).fillna(0.0)
        gross_returns = (effective_weights * returns).sum(axis=1)
        turnover = effective_weights.diff().abs().sum(axis=1).fillna(effective_weights.abs().sum(axis=1))
        cost_rate = (self.config.commission_bps + self.config.slippage_bps) / 10_000
        net_returns = gross_returns - turnover * cost_rate
        equity = (1.0 + net_returns).cumprod() * self.config.initial_cash

        return BacktestResult(
            equity_curve=equity.rename("equity"),
            daily_returns=net_returns.rename("return"),
            weights=weights,
            turnover=turnover.rename("turnover"),
            metrics=summarize_performance(equity),
        )
