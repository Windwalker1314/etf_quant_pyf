from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from etf_quant.config.schema import FactorConfig
from etf_quant.data.dataset import MarketData


@dataclass(frozen=True)
class MomentumFactor:
    window: int = 126
    name: str = "momentum"

    def compute(self, market_data: MarketData) -> pd.DataFrame:
        close = market_data.close_wide()
        return close.pct_change(self.window)


@dataclass(frozen=True)
class VolatilityFactor:
    window: int = 63
    name: str = "volatility"

    def compute(self, market_data: MarketData) -> pd.DataFrame:
        returns = market_data.returns()
        return returns.rolling(self.window).std() * (252**0.5)


@dataclass(frozen=True)
class MovingAverageGapFactor:
    window: int = 120
    name: str = "ma_gap"

    def compute(self, market_data: MarketData) -> pd.DataFrame:
        close = market_data.close_wide()
        ma = close.rolling(self.window).mean()
        return close / ma - 1.0


FACTOR_REGISTRY = {
    "momentum": MomentumFactor,
    "volatility": VolatilityFactor,
    "ma_gap": MovingAverageGapFactor,
}


def build_factors(configs: list[FactorConfig]):
    factors = []
    for config in configs:
        try:
            factor_cls = FACTOR_REGISTRY[config.name]
        except KeyError as exc:
            available = ", ".join(sorted(FACTOR_REGISTRY))
            raise ValueError(f"Unknown factor {config.name!r}. Available: {available}") from exc
        factors.append(factor_cls(**config.params))
    return factors


def compute_factor_panel(market_data: MarketData, configs: list[FactorConfig]) -> dict[str, pd.DataFrame]:
    return {factor.name: factor.compute(market_data) for factor in build_factors(configs)}
