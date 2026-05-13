from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from etf_quant.config.schema import FactorConfig
from etf_quant.data.dataset import MarketData


@dataclass(frozen=True)
class MomentumFactor:
    window: int = 126
    name: str = "momentum"

    def compute(self, market_data: MarketData) -> pd.DataFrame:
        close = market_data.close_wide()
        return close.pct_change(self.window)


@dataclass(frozen=True)
class VolatilityFactor:
    window: int = 63
    name: str = "volatility"

    def compute(self, market_data: MarketData) -> pd.DataFrame:
        returns = market_data.returns()
        return returns.rolling(self.window).std() * (252**0.5)


@dataclass(frozen=True)
class MovingAverageGapFactor:
    window: int = 120
    name: str = "ma_gap"

    def compute(self, market_data: MarketData) -> pd.DataFrame:
        close = market_data.close_wide()
        ma = close.rolling(self.window).mean()
        return close / ma - 1.0


def _trend_score_series(close: pd.Series, period: int = 25) -> pd.Series:
    close = close.astype(float)
    out = pd.Series(index=close.index, dtype=float)
    if len(close) < period:
        return out
    y = np.log(close.values)
    windows = np.lib.stride_tricks.sliding_window_view(y, window_shape=period)
    x = np.arange(period, dtype=float)
    n = period
    sum_x = x.sum()
    sum_x2 = (x**2).sum()
    denom = n * sum_x2 - sum_x**2
    sum_y = windows.sum(axis=1)
    sum_xy = (windows * x).sum(axis=1)
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    annualized = np.exp(slope * 250.0) - 1.0
    y_pred = slope[:, None] * x + intercept[:, None]
    resid = windows - y_pred
    ss_res = np.sum(resid**2, axis=1)
    sum_y2 = np.sum(windows**2, axis=1)
    ss_tot = sum_y2 - (sum_y**2) / n
    r2 = 1 - (ss_res / np.where(ss_tot == 0, np.nan, ss_tot))
    r2 = np.nan_to_num(r2, nan=0.0)
    score = annualized * r2
    if np.isfinite(score).sum() > 0:
        q1, q9 = np.nanpercentile(score, [5, 95])
        score = np.clip(score, q1, q9)
    out.iloc[period - 1 :] = score
    return out


def _tanh_transform(values: pd.DataFrame, scale: float, mode: str) -> pd.DataFrame:
    if mode == "center0.5":
        x = values - 0.5
    elif mode == "center50":
        x = values - 50.0
    elif mode == "minus1":
        x = values - 1.0
    elif mode == "zero_is_ok":
        x = values.fillna(0.0)
    else:
        x = values
    return np.tanh(x / max(scale, 1e-9)).fillna(0.0)


BIGQUANT_FACTOR_CFG = [
    ("trend_score", 1.00, 0.20, "raw"),
    ("mom_20", 0.45, 0.10, "raw"),
    ("mom_60", 0.15, 0.22, "raw"),
    ("ma_5_10", 0.35, 0.018, "raw"),
    ("ma_10_20", 0.20, 0.018, "raw"),
    ("don_pos_20", 0.55, 0.22, "center0.5"),
    ("dev_atr_20", 0.35, 0.90, "raw"),
    ("turn_accel_20", 0.20, 0.50, "raw"),
    ("amt_accel_20", 0.15, 0.50, "raw"),
    ("obv_balance_20", 0.25, 0.50, "raw"),
    ("mfi_14", 0.10, 20.0, "center50"),
    ("vol_ratio_10_60", -0.40, 0.25, "minus1"),
    ("downvar_60", -0.55, 1e-4, "raw"),
    ("ulcer_60", -0.55, 0.008, "raw"),
    ("gap_open", -0.10, 0.02, "raw"),
    ("candle_pos", 0.05, 0.50, "raw"),
    ("intraday_range", -0.08, 0.03, "raw"),
    ("premium_iopv", -0.50, 0.01, "zero_is_ok"),
]


@dataclass(frozen=True)
class BigQuantRotationFactor:
    trend_period: int = 25
    inv_vol_window: int = 30
    weight_clip_pct: float = 0.90
    name: str = "bigquant_rotation"

    def compute(self, market_data: MarketData) -> pd.DataFrame:
        ohlcv = market_data.prices.copy()
        close = market_data.close_wide()
        open_ = market_data.open_wide()
        high = ohlcv.pivot(index="date", columns="symbol", values="high").sort_index().ffill()
        low = ohlcv.pivot(index="date", columns="symbol", values="low").sort_index().ffill()
        volume = ohlcv.pivot(index="date", columns="symbol", values="volume").sort_index().ffill()
        turn = self._wide_or_default(ohlcv, "turn", volume)
        pre_close = close.shift(1)
        change_ratio = close.pct_change()
        amount = self._wide_or_default(ohlcv, "amount", close * volume)
        iopv = self._wide_or_default(
            ohlcv,
            "iopv",
            pd.DataFrame(np.nan, index=close.index, columns=close.columns),
        )

        true_range = pd.concat(
            [
                (high - low).stack(),
                (high - pre_close).abs().stack(),
                (low - pre_close).abs().stack(),
            ],
            axis=1,
        ).max(axis=1).unstack()
        atr_14 = true_range.rolling(14).mean()
        don_range_20 = high.rolling(20).max() - low.rolling(20).min()
        typical = (high + low + close) / 3.0
        positive_money = (typical * volume).where(typical > typical.shift(1), 0.0)
        negative_money = (typical * volume).where(typical < typical.shift(1), 0.0)
        mfi_den = positive_money.rolling(14).sum() + negative_money.rolling(14).sum()

        panels: dict[str, pd.DataFrame] = {
            "mom_20": close / close.shift(20) - 1.0,
            "mom_60": close / close.shift(60) - 1.0,
            "ma_5_10": close.rolling(5).mean() / close.rolling(10).mean() - 1.0,
            "ma_10_20": close.rolling(10).mean() / close.rolling(20).mean() - 1.0,
            "don_pos_20": ((close - low.rolling(20).min()) / don_range_20).replace([np.inf, -np.inf], 0.0),
            "dev_atr_20": ((close - close.rolling(20).mean()) / atr_14).replace([np.inf, -np.inf], 0.0),
            "vol_ratio_10_60": (change_ratio.rolling(10).std() / change_ratio.rolling(60).std()).replace(
                [np.inf, -np.inf], 0.0
            ),
            "downvar_60": change_ratio.where(change_ratio < 0, 0.0).pow(2).rolling(60).mean(),
            "ulcer_60": (close / close.rolling(60).max() - 1.0).pow(2).rolling(60).mean(),
            "turn_accel_20": turn / turn.rolling(20).mean() - 1.0,
            "amt_accel_20": amount / amount.rolling(20).mean() - 1.0,
            "obv_balance_20": volume.where(close > pre_close, -volume.where(close < pre_close, 0.0))
            .rolling(20)
            .sum()
            / volume.rolling(20).sum(),
            "mfi_14": (positive_money.rolling(14).sum() / mfi_den).replace([np.inf, -np.inf], 0.0),
            "gap_open": open_ / pre_close - 1.0,
            "candle_pos": ((close - open_) / (high - low)).replace([np.inf, -np.inf], 0.0),
            "intraday_range": ((high - low) / pre_close).replace([np.inf, -np.inf], 0.0),
            "premium_iopv": (close / iopv - 1.0).replace([np.inf, -np.inf], np.nan),
        }
        panels["trend_score"] = close.apply(lambda s: _trend_score_series(s, self.trend_period))
        vol_inv = change_ratio.rolling(self.inv_vol_window).std()
        inv_vol = (1.0 / vol_inv.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        inv_vol = inv_vol.apply(self._clip_inv_vol)

        score = pd.DataFrame(0.0, index=close.index, columns=close.columns)
        for column, weight, scale, mode in BIGQUANT_FACTOR_CFG:
            score = score + weight * _tanh_transform(panels[column], scale, mode)
        return pd.concat({"score": score.fillna(-1e9), "inv_vol": inv_vol}, axis=1)

    def _clip_inv_vol(self, values: pd.Series) -> pd.Series:
        if values.notna().sum() == 0:
            return values.fillna(1.0)
        high = values.quantile(self.weight_clip_pct)
        return values.clip(upper=high).fillna(values.median())

    @staticmethod
    def _wide_or_default(ohlcv: pd.DataFrame, column: str, default: pd.DataFrame) -> pd.DataFrame:
        if column not in ohlcv.columns:
            return default
        wide = ohlcv.pivot(index="date", columns="symbol", values=column).sort_index().ffill()
        return wide.reindex(index=default.index, columns=default.columns)


FACTOR_REGISTRY = {
    "bigquant_rotation": BigQuantRotationFactor,
    "momentum": MomentumFactor,
    "volatility": VolatilityFactor,
    "ma_gap": MovingAverageGapFactor,
}


def build_factors(configs: list[FactorConfig]):
    factors = []
    for config in configs:
        try:
            factor_cls = FACTOR_REGISTRY[config.name]
        except KeyError as exc:
            available = ", ".join(sorted(FACTOR_REGISTRY))
            raise ValueError(f"Unknown factor {config.name!r}. Available: {available}") from exc
        factors.append(factor_cls(**config.params))
    return factors


def compute_factor_panel(market_data: MarketData, configs: list[FactorConfig]) -> dict[str, pd.DataFrame]:
    return {factor.name: factor.compute(market_data) for factor in build_factors(configs)}
