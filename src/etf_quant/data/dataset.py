from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import pandas as pd


REQUIRED_PRICE_COLUMNS = {"date", "symbol", "open", "high", "low", "close", "volume"}


@dataclass(frozen=True)
class MarketData:
    prices: pd.DataFrame

    def __post_init__(self) -> None:
        missing = REQUIRED_PRICE_COLUMNS - set(self.prices.columns)
        if missing:
            raise ValueError(f"Missing price columns: {sorted(missing)}")

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> "MarketData":
        data = frame.copy()
        data = data.loc[:, ~data.columns.astype(str).str.startswith("Unnamed")]
        data["date"] = pd.to_datetime(data["date"])
        data = data.sort_values(["date", "symbol"]).reset_index(drop=True)
        return cls(data)

    def symbols(self) -> list[str]:
        return sorted(self.prices["symbol"].unique().tolist())

    def slice(
        self,
        start: Optional[pd.Timestamp | str] = None,
        end: Optional[pd.Timestamp | str] = None,
        symbols: Optional[Iterable[str]] = None,
    ) -> "MarketData":
        data = self.prices
        if start is not None:
            data = data[data["date"] >= pd.Timestamp(start)]
        if end is not None:
            data = data[data["date"] <= pd.Timestamp(end)]
        if symbols is not None:
            data = data[data["symbol"].isin(list(symbols))]
        return MarketData.from_frame(data)

    def close_wide(self) -> pd.DataFrame:
        return (
            self.prices.pivot(index="date", columns="symbol", values="close")
            .sort_index()
            .ffill()
        )

    def open_wide(self) -> pd.DataFrame:
        return (
            self.prices.pivot(index="date", columns="symbol", values="open")
            .sort_index()
            .ffill()
        )

    def ohlc_anomaly_ratio(self) -> float:
        price_cols = ["open", "high", "low", "close"]
        frame = self.prices[price_cols].apply(pd.to_numeric, errors="coerce")
        valid = frame.dropna()
        if valid.empty:
            return 0.0
        bad = (valid["high"] < valid[["open", "low", "close"]].max(axis=1)) | (
            valid["low"] > valid[["open", "high", "close"]].min(axis=1)
        )
        return float(bad.mean())

    def returns(self) -> pd.DataFrame:
        return self.close_wide().pct_change().fillna(0.0)
