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
    max_position_weight: float = 1.0
    max_bucket_weight: float = 1.0
    max_bucket_weights: dict[str, float] = field(default_factory=dict)
    bucket_map: dict[str, str] = field(default_factory=dict)
    bucket_group_caps: dict[str, float] = field(default_factory=dict)
    bucket_groups: dict[str, list[str]] = field(default_factory=dict)
    use_trend_state_budget: bool = False
    trend_budget_bucket: str = "US_EQUITY"
    trend_budget_group: str = "RISK_EQUITY"
    trend_budget_symbols: list[str] = field(default_factory=list)
    trend_defensive_symbols: list[str] = field(default_factory=list)
    trend_fast_ma_window: int = 120
    trend_slow_ma_window: int = 200
    trend_relative_window: int = 126
    trend_strong_relative_momentum: float = 0.00
    trend_weak_relative_momentum: float = -0.05
    trend_state_budgets: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            "strong": {"bucket_cap": 0.80, "group_cap": 0.90},
            "neutral": {"bucket_cap": 0.60, "group_cap": 0.80},
            "weak": {"bucket_cap": 0.40, "group_cap": 0.50},
        }
    )
    use_risk_overlay: bool = False
    risk_symbols: list[str] = field(default_factory=list)
    defensive_symbols: list[str] = field(default_factory=list)
    risk_ma_window: int = 120
    risk_breadth_threshold: float = 0.50
    risk_momentum_window: int = 63
    risk_momentum_threshold: float = -0.03
    defensive_cash_weight: float = 0.25
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

        risk_on = self._is_risk_on(as_of_date, close)
        if self.use_risk_overlay and not risk_on:
            day_score = self._defensive_score(day_score)
            held &= set(day_score.index)
            if day_score.empty:
                adjusted = pd.Series(0.0, index=close.columns)
                self.current_weights = adjusted
                return adjusted

        final = self._select_final_symbols(as_of_date, day_score, held)
        weights = self._target_weights(final, day_inv_vol, day_score, as_of_date=as_of_date)
        if self.use_risk_overlay and not risk_on and self.defensive_cash_weight > 0:
            deploy_weight = max(0.0, min(1.0, 1.0 - float(self.defensive_cash_weight)))
            weights = {symbol: weight * deploy_weight for symbol, weight in weights.items()}
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
        as_of_date: pd.Timestamp | None = None,
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
        bucket_overrides, group_overrides = self._trend_budget_overrides(as_of_date)
        weights = self._enforce_bucket_caps(weights, bucket_overrides)
        weights = self._enforce_bucket_group_caps(weights, group_overrides)
        weights = self._enforce_position_cap(weights)
        return weights.to_dict()

    def _is_risk_on(self, as_of_date: pd.Timestamp, close: pd.DataFrame) -> bool:
        if not self.use_risk_overlay:
            return True
        risk_symbols = [symbol for symbol in self.risk_symbols if symbol in close.columns]
        if not risk_symbols:
            return True
        history = close.loc[:as_of_date, risk_symbols]
        required = max(2, int(self.risk_ma_window), int(self.risk_momentum_window) + 1)
        if len(history) < required:
            return False

        latest = history.iloc[-1]
        ma = history.rolling(int(self.risk_ma_window)).mean().iloc[-1]
        breadth = float((latest > ma).mean())

        broad_proxy = history.mean(axis=1)
        lookback = max(1, int(self.risk_momentum_window))
        momentum = float(broad_proxy.iloc[-1] / broad_proxy.shift(lookback).iloc[-1] - 1.0)
        if not np.isfinite(momentum):
            momentum = -1.0
        return breadth >= float(self.risk_breadth_threshold) and momentum >= float(self.risk_momentum_threshold)

    def _defensive_score(self, day_score: pd.Series) -> pd.Series:
        allowed = [symbol for symbol in self.defensive_symbols if symbol in day_score.index]
        if not allowed:
            return day_score
        return day_score.reindex(allowed).dropna()

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

    def _bucket_map(self) -> dict[str, str]:
        return {str(symbol): str(bucket) for symbol, bucket in self.bucket_map.items()}

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

    def _enforce_position_cap(self, weights: pd.Series) -> pd.Series:
        cap = float(self.max_position_weight)
        if cap <= 0 or cap >= 1.0 or weights.empty:
            return weights
        weights = weights.clip(lower=0.0)
        for _ in range(len(weights)):
            over = weights[weights > cap + 1e-12]
            if over.empty:
                break
            excess = float((over - cap).sum())
            weights.loc[over.index] = cap
            room = (cap - weights).clip(lower=0.0)
            room = room[room > 1e-12]
            if room.empty or excess <= 1e-12:
                break
            add = room / float(room.sum()) * min(excess, float(room.sum()))
            weights.loc[add.index] = weights.loc[add.index] + add
        return weights

    def _enforce_bucket_caps(
        self,
        weights: pd.Series,
        cap_overrides: dict[str, float] | None = None,
    ) -> pd.Series:
        bucket_map = self._bucket_map()
        if not bucket_map:
            return weights
        default_cap = float(self.max_bucket_weight)
        bucket_caps = {str(bucket): float(cap) for bucket, cap in self.max_bucket_weights.items()}
        if cap_overrides:
            bucket_caps.update({str(bucket): float(cap) for bucket, cap in cap_overrides.items()})
        if default_cap >= 1.0 and all(cap >= 1.0 for cap in bucket_caps.values()):
            return weights

        labels = pd.Series({symbol: bucket_map.get(symbol, "OTHER") for symbol in weights.index})
        caps = {bucket: bucket_caps.get(bucket, default_cap) for bucket in labels.unique()}
        return self._enforce_group_caps(weights, labels, caps)

    def _enforce_bucket_group_caps(
        self,
        weights: pd.Series,
        cap_overrides: dict[str, float] | None = None,
    ) -> pd.Series:
        bucket_map = self._bucket_map()
        if not bucket_map or (not self.bucket_group_caps and not cap_overrides):
            return weights
        bucket_labels = pd.Series({symbol: bucket_map.get(symbol, "OTHER") for symbol in weights.index})
        adjusted = weights
        group_caps = {str(group): float(cap) for group, cap in self.bucket_group_caps.items()}
        if cap_overrides:
            group_caps.update({str(group): float(cap) for group, cap in cap_overrides.items()})
        for group_name, cap in group_caps.items():
            allowed_buckets = set(self.bucket_groups.get(group_name, []))
            if not allowed_buckets:
                continue
            labels = pd.Series(
                {
                    symbol: group_name if bucket_labels.loc[symbol] in allowed_buckets else "__REST__"
                    for symbol in adjusted.index
                }
            )
            adjusted = self._enforce_group_caps(adjusted, labels, {group_name: float(cap), "__REST__": 1.0})
        return adjusted

    def _trend_budget_overrides(
        self,
        as_of_date: pd.Timestamp | None,
    ) -> tuple[dict[str, float], dict[str, float]]:
        if not self.use_trend_state_budget or as_of_date is None:
            return {}, {}
        state = self._trend_budget_state(as_of_date)
        budget = self.trend_state_budgets.get(state, self.trend_state_budgets.get("neutral", {}))
        bucket_overrides: dict[str, float] = {}
        group_overrides: dict[str, float] = {}
        if "bucket_cap" in budget:
            bucket_overrides[str(self.trend_budget_bucket)] = float(budget["bucket_cap"])
        if "group_cap" in budget:
            group_overrides[str(self.trend_budget_group)] = float(budget["group_cap"])
        return bucket_overrides, group_overrides

    def _trend_budget_state(self, as_of_date: pd.Timestamp) -> str:
        close = self._close_panel
        bucket_map = self._bucket_map()
        if close is None or close.empty or not bucket_map:
            return "neutral"

        trend_symbols = [symbol for symbol in self.trend_budget_symbols if symbol in close.columns]
        if not trend_symbols:
            trend_symbols = [
                symbol for symbol, bucket in bucket_map.items() if bucket == self.trend_budget_bucket and symbol in close.columns
            ]
        if not trend_symbols:
            return "neutral"

        lookback = max(
            2,
            int(self.trend_fast_ma_window),
            int(self.trend_slow_ma_window),
            int(self.trend_relative_window) + 1,
        )
        history = close.loc[:as_of_date, trend_symbols].tail(lookback).dropna(how="all")
        if len(history) < lookback:
            return "neutral"

        trend_proxy = self._normalized_proxy(history)
        if trend_proxy.empty:
            return "neutral"

        fast_ma = float(trend_proxy.rolling(int(self.trend_fast_ma_window)).mean().iloc[-1])
        slow_ma = float(trend_proxy.rolling(int(self.trend_slow_ma_window)).mean().iloc[-1])
        latest = float(trend_proxy.iloc[-1])
        relative_momentum = self._relative_momentum(close, trend_proxy, as_of_date)
        if not np.isfinite(relative_momentum):
            return "neutral"

        above_fast = np.isfinite(fast_ma) and latest >= fast_ma
        above_slow = np.isfinite(slow_ma) and latest >= slow_ma
        strong = above_fast and above_slow and relative_momentum >= float(self.trend_strong_relative_momentum)
        weak = (not above_fast) or relative_momentum <= float(self.trend_weak_relative_momentum)
        if strong:
            return "strong"
        if weak:
            return "weak"
        return "neutral"

    def _relative_momentum(
        self,
        close: pd.DataFrame,
        trend_proxy: pd.Series,
        as_of_date: pd.Timestamp,
    ) -> float:
        lookback = max(1, int(self.trend_relative_window))
        defensive_symbols = [symbol for symbol in self.trend_defensive_symbols if symbol in close.columns]
        if defensive_symbols:
            defensive_history = close.loc[:as_of_date, defensive_symbols].tail(lookback + 1).dropna(how="all")
            defensive_proxy = self._normalized_proxy(defensive_history)
            if not defensive_proxy.empty:
                aligned = pd.concat([trend_proxy, defensive_proxy], axis=1).dropna()
                if len(aligned) > lookback:
                    relative = aligned.iloc[:, 0] / aligned.iloc[:, 1]
                    return float(relative.iloc[-1] / relative.shift(lookback).iloc[-1] - 1.0)
        if len(trend_proxy) <= lookback:
            return np.nan
        return float(trend_proxy.iloc[-1] / trend_proxy.shift(lookback).iloc[-1] - 1.0)

    @staticmethod
    def _normalized_proxy(history: pd.DataFrame) -> pd.Series:
        clean = history.replace([np.inf, -np.inf], np.nan).dropna(how="all")
        if clean.empty:
            return pd.Series(dtype=float)
        base = clean.ffill().bfill().iloc[0].replace(0, np.nan)
        normalized = clean.ffill().bfill().divide(base).replace([np.inf, -np.inf], np.nan)
        return normalized.mean(axis=1).dropna()

    @staticmethod
    def _enforce_group_caps(
        weights: pd.Series,
        labels: pd.Series,
        caps: dict[str, float],
    ) -> pd.Series:
        weights = weights.clip(lower=0.0)
        if weights.empty or float(weights.sum()) <= 0:
            return weights

        group_alloc = weights.groupby(labels).sum()
        group_caps = pd.Series(
            {group: max(0.0, float(caps.get(group, 1.0))) for group in group_alloc.index},
            dtype=float,
        )
        if float((group_alloc - group_caps).max()) <= 1e-12:
            return weights

        adjusted_alloc = group_alloc.copy()
        for _ in range(len(group_alloc)):
            over = adjusted_alloc[adjusted_alloc > group_caps + 1e-12]
            if over.empty:
                break
            excess = float((over - group_caps.loc[over.index]).sum())
            adjusted_alloc.loc[over.index] = group_caps.loc[over.index]

            room = (group_caps - adjusted_alloc).clip(lower=0.0)
            room = room[room > 1e-12]
            if room.empty or excess <= 1e-12:
                break
            base = group_alloc.loc[room.index].clip(lower=0.0)
            if float(base.sum()) <= 0:
                base = room
            add = base / float(base.sum()) * min(excess, float(room.sum()))
            adjusted_alloc.loc[add.index] = adjusted_alloc.loc[add.index] + add

        adjusted = weights.copy()
        for group, target_weight in adjusted_alloc.items():
            symbols = labels[labels == group].index
            current_weight = float(weights.loc[symbols].sum())
            if current_weight > 0:
                adjusted.loc[symbols] = weights.loc[symbols] * (float(target_weight) / current_weight)
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
