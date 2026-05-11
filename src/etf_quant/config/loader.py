from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from etf_quant.config.schema import (
    AppConfig,
    Asset,
    BacktestConfig,
    DataConfig,
    FactorConfig,
    StrategyConfig,
    WalkForwardConfig,
)


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    raw = _load_yaml(config_path)
    base_dir = config_path.parent

    universe = [Asset(**item) for item in raw.get("universe", [])]
    data_raw = raw.get("data", {})
    data_path = data_raw.get("path")
    if data_path is not None:
        path_value = Path(data_path)
        if not path_value.is_absolute():
            path_value = (base_dir / path_value).resolve()
        data_raw = {**data_raw, "path": path_value}

    output_dir = Path(raw.get("output_dir", "outputs"))
    if not output_dir.is_absolute():
        output_dir = (base_dir / output_dir).resolve()

    walk_forward_raw = raw.get("walk_forward")
    walk_forward = WalkForwardConfig(**walk_forward_raw) if walk_forward_raw else None

    return AppConfig(
        universe=universe,
        data=DataConfig(**data_raw),
        factors=[FactorConfig(**item) for item in raw.get("factors", [])],
        strategy=StrategyConfig(**raw.get("strategy", {})),
        backtest=BacktestConfig(**raw.get("backtest", {})),
        walk_forward=walk_forward,
        output_dir=output_dir,
    )


def load_universe(path: str | Path) -> List[Asset]:
    raw = _load_yaml(Path(path))
    return [Asset(**item) for item in raw.get("universe", [])]
