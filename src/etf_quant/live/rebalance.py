from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from etf_quant.config.schema import AppConfig
from etf_quant.data.dataset import MarketData
from etf_quant.factors.library import compute_factor_panel
from etf_quant.strategies.registry import build_strategy


@dataclass(frozen=True)
class RebalancePlan:
    as_of_date: pd.Timestamp
    target_weights: pd.Series
    plan: pd.DataFrame


def build_rebalance_plan(
    config: AppConfig,
    market_data: MarketData,
    current_weights: pd.Series | None = None,
) -> RebalancePlan:
    close = market_data.close_wide()
    as_of_date = close.index.max()
    strategy = build_strategy(config.strategy).fit(market_data)
    factors = compute_factor_panel(market_data, config.factors)
    target = strategy.generate_weights(as_of_date, market_data, factors).reindex(close.columns).fillna(0.0)
    current = current_weights.reindex(close.columns).fillna(0.0) if current_weights is not None else pd.Series(0.0, index=close.columns)
    plan = pd.DataFrame(
        {
            "symbol": close.columns,
            "current_weight": current.values,
            "target_weight": target.values,
            "trade_weight": (target - current).values,
        }
    )
    return RebalancePlan(as_of_date=as_of_date, target_weights=target, plan=plan)
