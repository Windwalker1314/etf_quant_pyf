from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Window:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def make_walk_forward_windows(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    train_months: int,
    validation_months: int,
    test_months: int,
    step_months: int,
    mode: str = "rolling",
) -> list[Window]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    windows: list[Window] = []
    anchor = start_ts
    while True:
        train_start = start_ts if mode == "expanding" else anchor
        train_end = anchor + pd.DateOffset(months=train_months) - pd.DateOffset(days=1)
        validation_start = train_end + pd.DateOffset(days=1)
        validation_end = validation_start + pd.DateOffset(months=validation_months) - pd.DateOffset(days=1)
        test_start = validation_end + pd.DateOffset(days=1)
        test_end = test_start + pd.DateOffset(months=test_months) - pd.DateOffset(days=1)
        if test_start > end_ts:
            break
        windows.append(
            Window(
                train_start=train_start,
                train_end=min(train_end, end_ts),
                validation_start=min(validation_start, end_ts),
                validation_end=min(validation_end, end_ts),
                test_start=min(test_start, end_ts),
                test_end=min(test_end, end_ts),
            )
        )
        if test_end >= end_ts:
            break
        anchor = anchor + pd.DateOffset(months=step_months)
    return windows
