from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd

from etf_quant.config.schema import DataConfig
from etf_quant.data.dataset import MarketData


class DataSource(Protocol):
    def load(self, config: DataConfig) -> MarketData:
        ...


class CsvDataSource:
    def load(self, config: DataConfig) -> MarketData:
        if config.path is None:
            raise ValueError("CSV data source requires data.path")
        frame = pd.read_csv(config.path)
        data = MarketData.from_frame(frame)
        return data.slice(config.start, config.end)


DATA_SOURCE_REGISTRY: dict[str, DataSource] = {
    "csv": CsvDataSource(),
}


def load_market_data(config: DataConfig) -> MarketData:
    try:
        source = DATA_SOURCE_REGISTRY[config.source]
    except KeyError as exc:
        available = ", ".join(sorted(DATA_SOURCE_REGISTRY))
        raise ValueError(f"Unknown data source {config.source!r}. Available: {available}") from exc
    return source.load(config)
