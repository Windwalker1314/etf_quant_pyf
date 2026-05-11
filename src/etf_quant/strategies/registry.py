from __future__ import annotations

from etf_quant.config.schema import StrategyConfig
from etf_quant.strategies.rules import MultiFactorRuleStrategy


STRATEGY_REGISTRY = {
    "multi_factor_rule": MultiFactorRuleStrategy,
}


def build_strategy(config: StrategyConfig):
    try:
        strategy_cls = STRATEGY_REGISTRY[config.name]
    except KeyError as exc:
        available = ", ".join(sorted(STRATEGY_REGISTRY))
        raise ValueError(f"Unknown strategy {config.name!r}. Available: {available}") from exc
    return strategy_cls(**config.params)
