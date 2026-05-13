from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from etf_quant.data.dataset import MarketData


DEFAULT_SPECIFIED_ETFS = [
    "160723.SZ",
    "513100.SH",
    "159985.SZ",
    "513500.SH",
    "518880.SH",
    "513130.SH",
    "510300.SH",
    "159915.SZ",
    "513600.SH",
]

DEFAULT_CLUSTERS = {
    "A": ["510300.SH", "159915.SZ", "513600.SH"],
    "US": ["513100.SH", "513500.SH", "159985.SZ", "513130.SH"],
    "ALT": ["518880.SH"],
    "BOND": ["160723.SZ"],
}


@dataclass
class BigQuantRotationStrategy:
    hold_num: int = 2
    rebalance_weekday: int | None = None
    score_gap_base: float = 0.10
    gap_coef: float = 0.35
    gap_floor: float = 0.10
    change_threshold: float = 0.10
    trail_stop_pct: float = 0.06
    hard_stop_pct: float = 0.06
    take_profit_pct: float | None = 0.40
    cool_days: int = 3
    min_hold_days: int = 0
    entry_confirm_days: int = 1
    entry_rank_buffer: int = 0
    use_inv_vol_weight: bool = True
    score_weight_strength: float = 0.0
    score_smoothing_window: int = 1
    max_cluster_weight: float = 0.80
    specified_etfs: list[str] = field(default_factory=lambda: DEFAULT_SPECIFIED_ETFS.copy())
    clusters: dict[str, list[str]] = field(default_factory=lambda: {k: v.copy() for k, v in DEFAULT_CLUSTERS.items()})

    name: str = "bigquant_rotation"

    def __post_init__(self) -> None:
        self.buy_price: dict[str, float] = {}
        self.high_since_buy: dict[str, float] = {}
        self.buy_date: dict[str, pd.Timestamp] = {}
        self.cool_until: dict[str, pd.Timestamp] = {}
        self.current_weights = pd.Series(dtype=float)
        self._score_panel: pd.DataFrame | None = None
        self._close_panel: pd.DataFrame | None = None

    def fit(
        self,
        train_data: MarketData,
        validation_data: MarketData | None = None,
    ) -> "BigQuantRotationStrategy":
        self._close_panel = train_data.close_wide()
        self.current_weights = pd.Series(0.0, index=train_data.symbols())
        return self

    def generate_weights(
        self,
        as_of_date: pd.Timestamp,
        market_data: MarketData,
        factor_data: dict[str, pd.DataFrame],
    ) -> pd.Series:
        if self._close_panel is None or self._close_panel.index.max() < pd.Timestamp(as_of_date):
            self._close_panel = market_data.close_wide()
        close = self._close_panel
        symbols = [symbol for symbol in close.columns if symbol in self.specified_etfs]
        if not symbols:
            symbols = list(close.columns)
        current = self.current_weights.reindex(close.columns).fillna(0.0)
        current = current.where(current.abs() >= 1e-12, 0.0)
        held = set(current[current > 0].index)
        latest_close = close.loc[:as_of_date].tail(1)
        if latest_close.empty:
            return current

        to_sell = self._apply_stops(as_of_date, latest_close.iloc[0], held)
        for symbol in to_sell:
            current.loc[symbol] = 0.0
            self._clear_position_state(symbol)
            self.cool_until[symbol] = self._next_business_date(as_of_date, self.cool_days)
        held -= to_sell

        if self.rebalance_weekday is not None and as_of_date.weekday() != self.rebalance_weekday:
            self.current_weights = current
            return current

        panel = factor_data.get("bigquant_rotation")
        if panel is None:
            raise ValueError("BigQuantRotationStrategy requires factor: bigquant_rotation")
        self._score_panel = panel["score"]
        score = panel["score"].loc[:as_of_date].tail(max(1, int(self.score_smoothing_window)))
        inv_vol = panel["inv_vol"].loc[:as_of_date].tail(1)
        if score.empty:
            self.current_weights = current
            return current

        day_score = score.mean().reindex(symbols).dropna()
        day_inv_vol = inv_vol.iloc[0].reindex(symbols) if not inv_vol.empty else pd.Series(1.0, index=symbols)
        if day_score.empty:
            self.current_weights = current
            return current

        final = self._select_final_symbols(as_of_date, day_score, held)
        weights = self._target_weights(final, day_inv_vol, day_score)
        target = pd.Series(0.0, index=close.columns)
        for symbol, weight in weights.items():
            target.loc[symbol] = weight

        adjusted = current.copy()
        for symbol in list(held):
            if symbol not in final:
                if self._can_exit(symbol, as_of_date):
                    adjusted.loc[symbol] = 0.0
                    self._clear_position_state(symbol)

        for symbol, target_weight in target[target > 0].items():
            current_weight = float(adjusted.get(symbol, 0.0))
            if abs(target_weight - current_weight) < self.change_threshold:
                continue
            adjusted.loc[symbol] = float(target_weight)
            px = float(latest_close.iloc[0].get(symbol, np.nan))
            if np.isfinite(px) and symbol not in self.buy_price:
                self.buy_price[symbol] = px
                self.high_since_buy[symbol] = px
                self.buy_date[symbol] = pd.Timestamp(as_of_date)

        adjusted = self._cap_gross_exposure(adjusted)
        self.current_weights = adjusted
        return adjusted

    def _apply_stops(
        self,
        as_of_date: pd.Timestamp,
        latest_close: pd.Series,
        held: set[str],
    ) -> set[str]:
        to_sell: set[str] = set()
        for symbol in list(held):
            px = latest_close.get(symbol)
            if px is None or not np.isfinite(px):
                continue
            px = float(px)
            self.buy_price.setdefault(symbol, px)
            self.high_since_buy.setdefault(symbol, px)
            self.high_since_buy[symbol] = max(self.high_since_buy[symbol], px)
            pnl = px / self.buy_price[symbol] - 1.0
            drawdown = px / self.high_since_buy[symbol] - 1.0
            if pnl <= -self.hard_stop_pct:
                to_sell.add(symbol)
                continue
            if drawdown <= -self.trail_stop_pct:
                to_sell.add(symbol)
                continue
            if self.take_profit_pct is not None and pnl >= self.take_profit_pct:
                to_sell.add(symbol)
        return to_sell

    def _select_final_symbols(
        self,
        as_of_date: pd.Timestamp,
        day_score: pd.Series,
        held: set[str],
    ) -> set[str]:
        gap_dyn = self.gap_coef * float(day_score.std(skipna=True)) if not day_score.empty else self.score_gap_base
        if not np.isfinite(gap_dyn):
            gap_dyn = self.score_gap_base
        gap_dyn = max(self.gap_floor, gap_dyn)

        ranked = day_score.sort_values(ascending=False)
        top_k = ranked.head(self.hold_num)
        kth = float(top_k.iloc[-1]) if len(top_k) else -1e9
        keepable = {symbol for symbol in held if symbol in day_score.index and (kth - float(day_score[symbol])) <= gap_dyn}

        final: list[str] = list(keepable)
        entry_pool = self._entry_pool(as_of_date, day_score)
        for symbol in top_k.index:
            if len(final) >= self.hold_num:
                break
            if symbol not in final and (symbol in held or symbol in entry_pool):
                final.append(symbol)

        cooling = {
            symbol
            for symbol, until in self.cool_until.items()
            if pd.Timestamp(until) >= pd.Timestamp(as_of_date)
        }
        return {symbol for symbol in final if symbol not in cooling}

    def _entry_pool(self, as_of_date: pd.Timestamp, day_score: pd.Series) -> set[str]:
        confirm_days = max(1, int(self.entry_confirm_days))
        rank_buffer = max(0, int(self.entry_rank_buffer))
        rank_cutoff = max(1, int(self.hold_num) + rank_buffer)
        if confirm_days <= 1:
            return set(day_score.sort_values(ascending=False).head(rank_cutoff).index)

        panel = self._score_panel
        if panel is None:
            return set(day_score.sort_values(ascending=False).head(rank_cutoff).index)
        history = panel.loc[:as_of_date].tail(confirm_days)
        if len(history) < confirm_days:
            return set()
        confirmed: set[str] = set(day_score.index)
        for _, row in history.iterrows():
            confirmed &= set(row.reindex(day_score.index).sort_values(ascending=False).head(rank_cutoff).index)
        return confirmed

    def _target_weights(
        self,
        symbols: set[str],
        inv_vol: pd.Series,
        score: pd.Series | None = None,
    ) -> dict[str, float]:
        if not symbols:
            return {}
        ordered = sorted(symbols)
        if self.use_inv_vol_weight:
            weights = inv_vol.reindex(ordered).replace([np.inf, -np.inf], np.nan).fillna(inv_vol.median())
            if weights.isna().all() or weights.sum() <= 0:
                weights = pd.Series(1.0, index=ordered)
            weights = weights / weights.sum()
        else:
            weights = pd.Series(1.0 / len(ordered), index=ordered)
        if score is not None and self.score_weight_strength > 0:
            weights = weights * self._score_tilt(score.reindex(ordered))

        cluster_map = self._cluster_map()
        weights = self._enforce_cluster_cap(weights, cluster_map)
        return weights.to_dict()

    def _score_tilt(self, score: pd.Series) -> pd.Series:
        clean = score.replace([np.inf, -np.inf], np.nan).astype(float)
        if clean.notna().sum() <= 1:
            return pd.Series(1.0, index=score.index)
        centered = clean - float(clean.mean(skipna=True))
        scale = float(clean.std(skipna=True, ddof=0))
        if not np.isfinite(scale) or scale <= 1e-12:
            return pd.Series(1.0, index=score.index)
        z = (centered / scale).clip(-2.0, 2.0).fillna(0.0)
        return np.exp(float(self.score_weight_strength) * z)

    def _cluster_map(self) -> dict[str, str]:
        return {symbol: cluster for cluster, symbols in self.clusters.items() for symbol in symbols}

    def _enforce_cluster_cap(self, weights: pd.Series, cluster_map: dict[str, str]) -> pd.Series:
        weights = weights.clip(lower=0.0)
        total = float(weights.sum())
        if total <= 0:
            return weights
        weights = weights / total
        cap = float(self.max_cluster_weight)
        if cap <= 0 or cap >= 1.0 or len(weights) <= 1:
            return weights

        labels = pd.Series({symbol: cluster_map.get(symbol, "OTHER") for symbol in weights.index})
        base_cluster = weights.groupby(labels).sum()
        if base_cluster.empty or float(base_cluster.max()) <= cap + 1e-12:
            return weights

        cluster_alloc = base_cluster.copy()
        capped: set[str] = set()
        for _ in range(len(base_cluster)):
            over = cluster_alloc[cluster_alloc > cap + 1e-12]
            if over.empty:
                break
            capped.update(over.index.tolist())
            cluster_alloc.loc[list(capped)] = cluster_alloc.loc[list(capped)].clip(upper=cap)
            uncapped = [cluster for cluster in cluster_alloc.index if cluster not in capped]
            residual = 1.0 - float(cluster_alloc.loc[list(capped)].sum())
            if residual <= 1e-12 or not uncapped:
                break
            base = base_cluster.loc[uncapped]
            if float(base.sum()) <= 0:
                break
            cluster_alloc.loc[uncapped] = residual * base / float(base.sum())

        adjusted = weights.copy()
        for cluster, target_weight in cluster_alloc.items():
            symbols = labels[labels == cluster].index
            current_weight = float(weights.loc[symbols].sum())
            if current_weight > 0:
                adjusted.loc[symbols] = weights.loc[symbols] * (float(target_weight) / current_weight)
        if adjusted.sum() > 0:
            adjusted = adjusted / adjusted.sum()
        return adjusted

    def _clear_position_state(self, symbol: str) -> None:
        self.buy_price.pop(symbol, None)
        self.high_since_buy.pop(symbol, None)
        self.buy_date.pop(symbol, None)

    def _can_exit(self, symbol: str, as_of_date: pd.Timestamp) -> bool:
        min_days = max(0, int(self.min_hold_days))
        if min_days <= 0 or symbol not in self.buy_date:
            return True
        held_days = len(pd.bdate_range(self.buy_date[symbol], pd.Timestamp(as_of_date))) - 1
        return held_days >= min_days

    @staticmethod
    def _cap_gross_exposure(weights: pd.Series) -> pd.Series:
        long_weights = weights.clip(lower=0.0)
        total = float(long_weights.sum())
        if total > 1.0:
            long_weights = long_weights / total
        return long_weights

    @staticmethod
    def _next_business_date(as_of_date: pd.Timestamp, days: int) -> pd.Timestamp:
        dates = pd.bdate_range(pd.Timestamp(as_of_date), periods=days + 1)
        return dates[-1]
