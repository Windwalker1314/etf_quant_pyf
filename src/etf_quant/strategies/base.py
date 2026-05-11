from __future__ import annotations

from typing import Optional, Protocol

import pandas as pd

from etf_quant.data.dataset import MarketData


class Strategy(Protocol):
    name: str

    def fit(
        self,
        train_data: MarketData,
        validation_data: Optional[MarketData] = None,
    ) -> "Strategy":
        ...

    def generate_weights(
        self,
        as_of_date: pd.Timestamp,
        market_data: MarketData,
        factor_data: dict[str, pd.DataFrame],
    ) -> pd.Series:
        ...
