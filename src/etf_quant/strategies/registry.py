from __future__ import annotations

from etf_quant.config.schema import StrategyConfig
from etf_quant.strategies.bigquant_rotation import BigQuantRotationStrategy
from etf_quant.strategies.rules import (
    EqualWeightStrategy,
    MacroRiskRotationStrategy,
    MomentumRotationStrategy,
    MultiFactorRuleStrategy,
    TopAnnualizedReturnStrategy,
)


STRATEGY_REGISTRY = {
    "bigquant_rotation": BigQuantRotationStrategy,
    "equal_weight": EqualWeightStrategy,
    "macro_risk_rotation": MacroRiskRotationStrategy,
    "momentum_rotation": MomentumRotationStrategy,
    "multi_factor_rule": MultiFactorRuleStrategy,
    "top_annualized_return": TopAnnualizedReturnStrategy,
}


def build_strategy(config: StrategyConfig):
    try:
        strategy_cls = STRATEGY_REGISTRY[config.name]
    except KeyError as exc:
        available = ", ".join(sorted(STRATEGY_REGISTRY))
        raise ValueError(f"Unknown strategy {config.name!r}. Available: {available}") from exc
    return strategy_cls(**config.params)
