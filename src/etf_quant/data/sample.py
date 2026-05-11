from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from etf_quant.config.schema import Asset


def generate_sample_prices(
    assets: Iterable[Asset],
    start: str = "2018-01-01",
    end: str = "2024-12-31",
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, end=end)
    rows = []
    for idx, asset in enumerate(assets):
        drift = 0.00015 + idx * 0.00001
        vol = 0.010 + (idx % 5) * 0.002
        shocks = rng.normal(drift, vol, size=len(dates))
        close = 100 * np.exp(np.cumsum(shocks))
        overnight = rng.normal(0.0, vol / 4, size=len(dates))
        open_ = close * (1 + overnight)
        high = np.maximum(open_, close) * (1 + rng.uniform(0, vol, len(dates)))
        low = np.minimum(open_, close) * (1 - rng.uniform(0, vol, len(dates)))
        volume = rng.integers(500_000, 5_000_000, size=len(dates))
        rows.extend(
            {
                "date": date,
                "symbol": asset.symbol,
                "open": open_[i],
                "high": high[i],
                "low": low[i],
                "close": close[i],
                "volume": volume[i],
            }
            for i, date in enumerate(dates)
        )
    return pd.DataFrame(rows)


def write_sample_prices(path: str | Path, assets: Iterable[Asset]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    generate_sample_prices(assets).to_csv(output, index=False)
    return output
