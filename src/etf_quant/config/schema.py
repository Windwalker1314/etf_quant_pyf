from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str
    asset_class: str
    currency: str = "CNY"


@dataclass(frozen=True)
class DataConfig:
    source: str
    path: Optional[Path] = None
    start: Optional[str] = None
    end: Optional[str] = None


@dataclass(frozen=True)
class FactorConfig:
    name: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 1_000_000.0
    commission_bps: float = 2.0
    slippage_bps: float = 1.0
    rebalance: str = "M"
    execution: str = "next_close"


@dataclass(frozen=True)
class WalkForwardConfig:
    train_months: int
    validation_months: int
    test_months: int
    step_months: int
    mode: str = "rolling"


@dataclass(frozen=True)
class AppConfig:
    universe: List[Asset]
    data: DataConfig
    factors: List[FactorConfig]
    strategy: StrategyConfig
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    walk_forward: Optional[WalkForwardConfig] = None
    output_dir: Path = Path("outputs")
