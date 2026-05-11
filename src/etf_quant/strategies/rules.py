from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from etf_quant.data.dataset import MarketData


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
