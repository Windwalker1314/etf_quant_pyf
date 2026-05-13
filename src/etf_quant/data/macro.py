from __future__ import annotations

from pathlib import Path
import time
from urllib.request import Request, urlopen

import pandas as pd


FRED_CSV_URLS = [
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
    "https://alfred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
]


def download_fred_series(series_ids: list[str], retries: int = 3, sleep_seconds: float = 1.0) -> pd.DataFrame:
    frames = []
    for series_id in series_ids:
        frames.append(_download_one_fred_series(series_id, retries=retries, sleep_seconds=sleep_seconds))
    if not frames:
        return pd.DataFrame(columns=["date"])
    data = frames[0]
    for frame in frames[1:]:
        data = data.merge(frame, on="date", how="outer")
    return data.sort_values("date").reset_index(drop=True)


def load_macro_series(path: str | Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    if "date" not in data.columns:
        raise ValueError("macro data must contain a date column")
    data["date"] = pd.to_datetime(data["date"])
    return data.sort_values("date").reset_index(drop=True)


def save_macro_series(data: pd.DataFrame, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = data.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame.to_csv(output, index=False)


def macro_from_price_ratio(
    prices: pd.DataFrame,
    numerator: str,
    denominator: str,
    output_col: str,
) -> pd.DataFrame:
    close = prices.pivot(index="date", columns="symbol", values="close").sort_index().ffill()
    missing = [symbol for symbol in (numerator, denominator) if symbol not in close.columns]
    if missing:
        raise ValueError(f"Missing symbols for macro ratio: {missing}")
    ratio = close[numerator] / close[denominator]
    return pd.DataFrame({"date": ratio.index, output_col: ratio.values})


def _download_one_fred_series(series_id: str, retries: int, sleep_seconds: float) -> pd.DataFrame:
    last_error: Exception | None = None
    for template in FRED_CSV_URLS:
        url = template.format(series_id=series_id)
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        for attempt in range(1, retries + 1):
            try:
                with urlopen(request, timeout=45) as response:
                    frame = pd.read_csv(response)
                break
            except Exception as exc:  # noqa: BLE001 - retry transient network failures.
                last_error = exc
                if attempt < retries:
                    time.sleep(sleep_seconds)
        else:
            continue
        break
    else:
        raise RuntimeError(f"FRED download failed for {series_id}: {last_error}")
    if "observation_date" in frame.columns:
        frame = frame.rename(columns={"observation_date": "date"})
    if "date" not in frame.columns or series_id not in frame.columns:
        raise RuntimeError(f"Unexpected FRED CSV format for {series_id}")
    out = frame[["date", series_id]].copy()
    out["date"] = pd.to_datetime(out["date"])
    out[series_id] = pd.to_numeric(out[series_id].replace(".", pd.NA), errors="coerce")
    return out
