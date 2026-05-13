from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from etf_quant.data.dataset import MarketData
from etf_quant.data.macro import load_macro_series


@dataclass
class MultiFactorRuleStrategy:
    top_n: int = 4
    factor_weights: dict[str, float] = field(
        default_factory=lambda: {"momentum": 1.0, "ma_gap": 0.5, "volatility": -0.7}
    )
    min_score_quantile: float = 0.0
    max_weight: float = 0.35
    cash_symbol: str | None = None

    name: str = "multi_factor_rule"

    def fit(
        self,
        train_data: MarketData,
        validation_data: MarketData | None = None,
    ) -> "MultiFactorRuleStrategy":
        return self

    def generate_weights(
        self,
        as_of_date: pd.Timestamp,
        market_data: MarketData,
        factor_data: dict[str, pd.DataFrame],
    ) -> pd.Series:
        symbols = market_data.symbols()
        score = pd.Series(0.0, index=symbols)
        for factor_name, weight in self.factor_weights.items():
            if factor_name not in factor_data:
                continue
            latest = factor_data[factor_name].loc[:as_of_date].tail(1)
            if latest.empty:
                continue
            values = latest.iloc[0].reindex(symbols)
            ranked = values.rank(pct=True, na_option="keep")
            score = score.add(ranked.fillna(0.0) * weight, fill_value=0.0)

        eligible = score.dropna()
        if eligible.empty:
            return pd.Series(0.0, index=symbols)

        threshold = eligible.quantile(self.min_score_quantile)
        selected = eligible[eligible >= threshold].sort_values(ascending=False).head(self.top_n)
        if selected.empty:
            return pd.Series(0.0, index=symbols)

        raw = pd.Series(0.0, index=symbols)
        raw.loc[selected.index] = 1.0 / len(selected)
        capped = raw.clip(upper=self.max_weight)
        unallocated = 1.0 - capped.sum()
        if unallocated > 1e-12:
            uncapped = capped[(capped > 0) & (capped < self.max_weight)]
            if not uncapped.empty:
                capped.loc[uncapped.index] = (
                    capped.loc[uncapped.index] + unallocated / len(uncapped)
                ).clip(upper=self.max_weight)

        if self.cash_symbol and self.cash_symbol in capped.index:
            capped.loc[self.cash_symbol] += max(0.0, 1.0 - capped.sum())
        return capped


@dataclass
class EqualWeightStrategy:
    symbols: list[str] | None = None

    name: str = "equal_weight"

    def fit(
        self,
        train_data: MarketData,
        validation_data: MarketData | None = None,
    ) -> "EqualWeightStrategy":
        return self

    def generate_weights(
        self,
        as_of_date: pd.Timestamp,
        market_data: MarketData,
        factor_data: dict[str, pd.DataFrame],
    ) -> pd.Series:
        close = market_data.close_wide()
        available = close.loc[:as_of_date].tail(1).dropna(axis=1).columns.tolist()
        symbols = [symbol for symbol in available if self.symbols is None or symbol in self.symbols]
        weights = pd.Series(0.0, index=close.columns)
        if symbols:
            weights.loc[symbols] = 1.0 / len(symbols)
        return weights


@dataclass
class TopAnnualizedReturnStrategy:
    top_n: int = 2
    symbols: list[str] | None = None

    name: str = "top_annualized_return"

    def __post_init__(self) -> None:
        self.selected_symbols: list[str] = []

    def fit(
        self,
        train_data: MarketData,
        validation_data: MarketData | None = None,
    ) -> "TopAnnualizedReturnStrategy":
        close = train_data.close_wide()
        candidates = close.columns if self.symbols is None else [s for s in self.symbols if s in close.columns]
        scores: dict[str, float] = {}
        for symbol in candidates:
            series = close[symbol].dropna()
            if len(series) < 2:
                continue
            years = len(series) / 252
            total_return = float(series.iloc[-1] / series.iloc[0] - 1.0)
            scores[symbol] = float((1.0 + total_return) ** (1.0 / years) - 1.0)
        self.selected_symbols = [
            symbol for symbol, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[: self.top_n]
        ]
        return self

    def generate_weights(
        self,
        as_of_date: pd.Timestamp,
        market_data: MarketData,
        factor_data: dict[str, pd.DataFrame],
    ) -> pd.Series:
        close = market_data.close_wide()
        latest = close.loc[:as_of_date].tail(1)
        weights = pd.Series(0.0, index=close.columns)
        if latest.empty:
            return weights
        tradable = [
            symbol
            for symbol in self.selected_symbols
            if symbol in latest.columns and np.isfinite(float(latest.iloc[0][symbol]))
        ]
        if tradable:
            weights.loc[tradable] = 1.0 / len(tradable)
        return weights


@dataclass
class MomentumRotationStrategy:
    hold_num: int = 3
    momentum_windows: list[int] = field(default_factory=lambda: [63, 126, 252])
    volatility_window: int = 63
    min_momentum: float = 0.0
    use_inv_vol_weight: bool = True
    score_smoothing_window: int = 1
    symbols: list[str] | None = None

    name: str = "momentum_rotation"

    def fit(
        self,
        train_data: MarketData,
        validation_data: MarketData | None = None,
    ) -> "MomentumRotationStrategy":
        close = train_data.close_wide()
        score = pd.DataFrame(0.0, index=close.index, columns=close.columns)
        counts = pd.DataFrame(0.0, index=close.index, columns=close.columns)
        for window in self.momentum_windows:
            mom = close / close.shift(window) - 1.0
            score = score.add(mom.fillna(0.0), fill_value=0.0)
            counts = counts.add(mom.notna().astype(float), fill_value=0.0)
        self.score_panel = score / counts.replace(0.0, np.nan)
        if self.score_smoothing_window > 1:
            self.score_panel = self.score_panel.rolling(int(self.score_smoothing_window)).mean()
        vol = close.pct_change().rolling(self.volatility_window).std()
        self.inv_vol_panel = (1.0 / vol.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
        return self

    def generate_weights(
        self,
        as_of_date: pd.Timestamp,
        market_data: MarketData,
        factor_data: dict[str, pd.DataFrame],
    ) -> pd.Series:
        close = market_data.close_wide()
        weights = pd.Series(0.0, index=close.columns)
        if not hasattr(self, "score_panel") or not hasattr(self, "inv_vol_panel"):
            self.fit(market_data)
        score_history = self.score_panel.loc[:as_of_date]
        if score_history.empty:
            return weights

        candidates = close.columns if self.symbols is None else [s for s in self.symbols if s in close.columns]
        score = score_history.iloc[-1].reindex(candidates)
        selected = score[score > self.min_momentum].dropna().sort_values(ascending=False).head(self.hold_num)
        if selected.empty:
            return weights

        if self.use_inv_vol_weight:
            raw = self.inv_vol_panel.loc[:as_of_date].tail(1).iloc[0].reindex(selected.index)
            raw = raw.fillna(raw.median())
            if raw.isna().all() or float(raw.sum()) <= 0:
                raw = pd.Series(1.0, index=selected.index)
            raw = raw / float(raw.sum())
        else:
            raw = pd.Series(1.0 / len(selected), index=selected.index)
        weights.loc[raw.index] = raw
        return weights


@dataclass
class MacroRiskRotationStrategy:
    risk_symbols: list[str] = field(default_factory=lambda: ["SPY", "QQQ", "IWM", "EFA", "EEM", "FXI", "VNQ"])
    defensive_symbols: list[str] = field(default_factory=lambda: ["IEF", "TLT", "GLD"])
    hold_num: int = 3
    defensive_hold_num: int = 2
    momentum_windows: list[int] = field(default_factory=lambda: [63, 126, 252])
    risk_ma_window: int = 200
    breadth_window: int = 200
    breadth_threshold: float = 0.55
    risk_score_threshold: float = 0.0
    crash_momentum_window: int = 63
    crash_momentum_threshold: float = -0.08
    volatility_window: int = 63
    min_risk_momentum: float = 0.0
    min_defensive_momentum: float = -1.0
    use_inv_vol_weight: bool = True
    cash_weight_when_defensive: float = 0.0
    safe_asset: str | None = "IEF"
    macro_data_path: str | None = None
    macro_lag_days: int = 21
    use_macro_filter: bool = False
    yield_curve_col: str = "T10Y2Y"
    credit_spread_col: str = "BAMLH0A0HYM2"
    financial_conditions_col: str = "NFCI"
    fed_funds_col: str = "FEDFUNDS"
    min_yield_curve: float | None = None
    max_credit_spread: float | None = None
    max_credit_spread_change_63d: float | None = None
    max_financial_conditions: float | None = None
    max_fed_funds_change_252d: float | None = None
    macro_trend_col: str | None = None
    macro_trend_ma_window: int = 126
    macro_trend_min_gap: float | None = None
    macro_trend_min_momentum_63d: float | None = None

    name: str = "macro_risk_rotation"

    def fit(
        self,
        train_data: MarketData,
        validation_data: MarketData | None = None,
    ) -> "MacroRiskRotationStrategy":
        close = train_data.close_wide()
        self.close_panel = close
        self.momentum_panel = self._momentum_score(close)
        self.inv_vol_panel = self._inv_vol(close)
        self.macro_panel = self._load_macro_panel(close.index)
        return self

    def generate_weights(
        self,
        as_of_date: pd.Timestamp,
        market_data: MarketData,
        factor_data: dict[str, pd.DataFrame],
    ) -> pd.Series:
        close = market_data.close_wide()
        if not hasattr(self, "momentum_panel") or self.close_panel.index.max() < pd.Timestamp(as_of_date):
            self.fit(market_data)

        weights = pd.Series(0.0, index=close.columns)
        date = self._last_available_date(pd.Timestamp(as_of_date))
        if date is None:
            return weights

        risk_on = self._is_risk_on(date)
        if risk_on:
            selected = self._select_symbols(
                date=date,
                symbols=self.risk_symbols,
                hold_num=self.hold_num,
                min_momentum=self.min_risk_momentum,
            )
            if not selected.empty:
                weights.loc[selected.index] = self._allocation(date, selected.index)
                return weights

        selected = self._select_symbols(
            date=date,
            symbols=self.defensive_symbols,
            hold_num=self.defensive_hold_num,
            min_momentum=self.min_defensive_momentum,
        )
        deploy_weight = max(0.0, min(1.0, 1.0 - float(self.cash_weight_when_defensive)))
        if selected.empty:
            if self.safe_asset in weights.index and deploy_weight > 0:
                weights.loc[self.safe_asset] = deploy_weight
            return weights
        weights.loc[selected.index] = self._allocation(date, selected.index) * deploy_weight
        return weights

    def _momentum_score(self, close: pd.DataFrame) -> pd.DataFrame:
        score = pd.DataFrame(0.0, index=close.index, columns=close.columns)
        counts = pd.DataFrame(0.0, index=close.index, columns=close.columns)
        for window in self.momentum_windows:
            momentum = close / close.shift(window) - 1.0
            score = score.add(momentum.fillna(0.0), fill_value=0.0)
            counts = counts.add(momentum.notna().astype(float), fill_value=0.0)
        return score / counts.replace(0.0, np.nan)

    def _inv_vol(self, close: pd.DataFrame) -> pd.DataFrame:
        vol = close.pct_change().rolling(self.volatility_window).std()
        return (1.0 / vol.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)

    def _last_available_date(self, as_of_date: pd.Timestamp) -> pd.Timestamp | None:
        history = self.close_panel.loc[:as_of_date]
        if history.empty:
            return None
        return pd.Timestamp(history.index[-1])

    def _is_risk_on(self, date: pd.Timestamp) -> bool:
        close = self.close_panel
        available_risk = [symbol for symbol in self.risk_symbols if symbol in close.columns]
        if not available_risk:
            return False

        risk_close = close.loc[:date, available_risk]
        if len(risk_close) <= max(self.risk_ma_window, self.breadth_window):
            return False

        latest = risk_close.iloc[-1]
        ma = risk_close.rolling(self.risk_ma_window).mean().iloc[-1]
        breadth = (latest > ma).mean()

        score = self.momentum_panel.loc[:date].iloc[-1].reindex(available_risk).mean(skipna=True)
        if not np.isfinite(score):
            score = -1.0

        crash_window = max(1, int(self.crash_momentum_window))
        broad_proxy = risk_close.mean(axis=1)
        crash_momentum = float(broad_proxy.iloc[-1] / broad_proxy.shift(crash_window).iloc[-1] - 1.0)
        if not np.isfinite(crash_momentum):
            crash_momentum = -1.0

        return (
            float(breadth) >= float(self.breadth_threshold)
            and float(score) >= float(self.risk_score_threshold)
            and crash_momentum >= float(self.crash_momentum_threshold)
            and self._macro_allows_risk(date)
        )

    def _load_macro_panel(self, target_index: pd.DatetimeIndex) -> pd.DataFrame | None:
        if not self.macro_data_path:
            return None
        macro = load_macro_series(self._resolve_macro_path(self.macro_data_path)).set_index("date").sort_index()
        shifted = macro.shift(max(0, int(self.macro_lag_days)), freq="D")
        aligned = shifted.reindex(target_index.union(shifted.index)).sort_index().ffill()
        return aligned.reindex(target_index).ffill()

    @staticmethod
    def _resolve_macro_path(path: str) -> Path:
        raw = Path(path)
        if raw.is_absolute() or raw.exists():
            return raw
        config_relative = Path("configs") / raw
        if config_relative.exists():
            return config_relative
        return raw

    def _macro_allows_risk(self, date: pd.Timestamp) -> bool:
        if not self.use_macro_filter:
            return True
        macro = getattr(self, "macro_panel", None)
        if macro is None or macro.empty:
            return True
        history = macro.loc[:date]
        if history.empty:
            return True
        row = history.iloc[-1]

        if self.min_yield_curve is not None and self.yield_curve_col in row.index:
            value = row[self.yield_curve_col]
            if np.isfinite(value) and float(value) < float(self.min_yield_curve):
                return False

        if self.max_credit_spread is not None and self.credit_spread_col in row.index:
            value = row[self.credit_spread_col]
            if np.isfinite(value) and float(value) > float(self.max_credit_spread):
                return False

        if self.max_credit_spread_change_63d is not None and self.credit_spread_col in macro.columns:
            series = history[self.credit_spread_col].dropna()
            if len(series) > 63:
                change = float(series.iloc[-1] - series.iloc[-64])
                if np.isfinite(change) and change > float(self.max_credit_spread_change_63d):
                    return False

        if self.max_financial_conditions is not None and self.financial_conditions_col in row.index:
            value = row[self.financial_conditions_col]
            if np.isfinite(value) and float(value) > float(self.max_financial_conditions):
                return False

        if self.max_fed_funds_change_252d is not None and self.fed_funds_col in macro.columns:
            series = history[self.fed_funds_col].dropna()
            if len(series) > 252:
                change = float(series.iloc[-1] - series.iloc[-253])
                if np.isfinite(change) and change > float(self.max_fed_funds_change_252d):
                    return False

        if self.macro_trend_col and self.macro_trend_col in macro.columns:
            series = history[self.macro_trend_col].dropna()
            window = max(2, int(self.macro_trend_ma_window))
            if len(series) >= window:
                latest = float(series.iloc[-1])
                ma = float(series.tail(window).mean())
                if self.macro_trend_min_gap is not None and ma > 0:
                    gap = latest / ma - 1.0
                    if np.isfinite(gap) and gap < float(self.macro_trend_min_gap):
                        return False
            if self.macro_trend_min_momentum_63d is not None and len(series) > 63:
                momentum = float(series.iloc[-1] / series.iloc[-64] - 1.0)
                if np.isfinite(momentum) and momentum < float(self.macro_trend_min_momentum_63d):
                    return False

        return True

    def _select_symbols(
        self,
        date: pd.Timestamp,
        symbols: list[str],
        hold_num: int,
        min_momentum: float,
    ) -> pd.Series:
        candidates = [symbol for symbol in symbols if symbol in self.momentum_panel.columns]
        if not candidates:
            return pd.Series(dtype=float)
        score = self.momentum_panel.loc[:date].iloc[-1].reindex(candidates)
        return score[score > min_momentum].dropna().sort_values(ascending=False).head(max(1, int(hold_num)))

    def _allocation(self, date: pd.Timestamp, symbols: pd.Index) -> pd.Series:
        if len(symbols) == 0:
            return pd.Series(dtype=float)
        if self.use_inv_vol_weight:
            raw = self.inv_vol_panel.loc[:date].iloc[-1].reindex(symbols)
            raw = raw.fillna(raw.median())
            if raw.isna().all() or float(raw.sum()) <= 0:
                raw = pd.Series(1.0, index=symbols)
            return raw / float(raw.sum())
        return pd.Series(1.0 / len(symbols), index=symbols)
