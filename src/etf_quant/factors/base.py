from __future__ import annotations

from typing import Protocol

import pandas as pd

from etf_quant.data.dataset import MarketData


class Factor(Protocol):
    name: str

    def compute(self, market_data: MarketData) -> pd.DataFrame:
        ...
