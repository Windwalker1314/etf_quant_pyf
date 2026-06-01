import unittest

import pandas as pd

from etf_quant.backtest.engine import BacktestEngine
from etf_quant.config.schema import Asset, BacktestConfig, FactorConfig, StrategyConfig
from etf_quant.data.dataset import MarketData
from etf_quant.data.sample import generate_sample_prices
from etf_quant.factors.library import compute_factor_panel
from etf_quant.strategies.bigquant_rotation import BigQuantRotationStrategy
from etf_quant.strategies.registry import build_strategy


class BigQuantRotationTests(unittest.TestCase):
    def _market_data_from_close(self, close: pd.DataFrame) -> MarketData:
        rows = []
        for date, values in close.iterrows():
            for symbol, price in values.items():
                rows.append(
                    {
                        "date": date,
                        "symbol": symbol,
                        "open": price,
                        "high": price,
                        "low": price,
                        "close": price,
                        "volume": 1_000_000,
                    }
                )
        return MarketData.from_frame(pd.DataFrame(rows))

    def test_factor_panel_contains_score_and_inv_vol(self):
        assets = [
            Asset(symbol="510300.SH", name="CSI 300", asset_class="cn_equity"),
            Asset(symbol="159915.SZ", name="ChiNext", asset_class="cn_equity"),
            Asset(symbol="518880.SH", name="Gold", asset_class="commodity"),
        ]
        data = MarketData.from_frame(generate_sample_prices(assets, start="2020-01-01", end="2021-12-31"))
        factors = compute_factor_panel(data, [FactorConfig(name="bigquant_rotation", params={})])

        panel = factors["bigquant_rotation"]

        self.assertIn("score", panel.columns.get_level_values(0))
        self.assertIn("inv_vol", panel.columns.get_level_values(0))

    def test_bigquant_rotation_backtest_runs_daily(self):
        assets = [
            Asset(symbol="510300.SH", name="CSI 300", asset_class="cn_equity"),
            Asset(symbol="159915.SZ", name="ChiNext", asset_class="cn_equity"),
            Asset(symbol="518880.SH", name="Gold", asset_class="commodity"),
        ]
        data = MarketData.from_frame(generate_sample_prices(assets, start="2020-01-01", end="2022-12-31"))
        strategy = build_strategy(
            StrategyConfig(
                name="bigquant_rotation",
                params={
                    "hold_num": 2,
                    "specified_etfs": [asset.symbol for asset in assets],
                    "clusters": {"A": ["510300.SH", "159915.SZ"], "ALT": ["518880.SH"]},
                },
            )
        ).fit(data)

        result = BacktestEngine(BacktestConfig(rebalance="D")).run(
            data,
            [FactorConfig(name="bigquant_rotation", params={})],
            strategy,
        )

        self.assertFalse(result.equity_curve.empty)
        self.assertGreater(result.equity_curve.iloc[-1], 0)
        self.assertIn("max_drawdown", result.metrics)

    def test_cluster_cap_is_respected_after_normalization(self):
        strategy = BigQuantRotationStrategy(
            use_inv_vol_weight=False,
            max_cluster_weight=0.60,
            clusters={"US": ["AAA", "BBB"], "ALT": ["CCC"]},
        )

        weights = strategy._target_weights(
            {"AAA", "BBB", "CCC"},
            pd.Series({"AAA": 2.0, "BBB": 2.0, "CCC": 1.0}),
        )

        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertLessEqual(weights["AAA"] + weights["BBB"], 0.60 + 1e-12)

    def test_score_tilt_overweights_stronger_score(self):
        strategy = BigQuantRotationStrategy(
            use_inv_vol_weight=False,
            score_weight_strength=0.5,
            max_cluster_weight=1.0,
        )

        weights = strategy._target_weights(
            {"AAA", "BBB"},
            pd.Series(1.0, index=["AAA", "BBB"]),
            pd.Series({"AAA": 2.0, "BBB": 1.0}),
        )

        self.assertGreater(weights["AAA"], weights["BBB"])

    def test_position_cap_leaves_cash_when_no_room_to_redistribute(self):
        strategy = BigQuantRotationStrategy(
            use_inv_vol_weight=False,
            max_cluster_weight=1.0,
            max_position_weight=0.60,
        )

        weights = strategy._target_weights(
            {"AAA"},
            pd.Series(1.0, index=["AAA"]),
        )

        self.assertAlmostEqual(weights["AAA"], 0.60)

    def test_bucket_cap_leaves_cash_when_all_selected_assets_share_bucket(self):
        strategy = BigQuantRotationStrategy(
            use_inv_vol_weight=False,
            max_cluster_weight=1.0,
            max_bucket_weight=0.60,
            bucket_map={"AAA": "US_EQUITY", "BBB": "US_EQUITY"},
        )

        weights = strategy._target_weights(
            {"AAA", "BBB"},
            pd.Series(1.0, index=["AAA", "BBB"]),
        )

        self.assertAlmostEqual(weights["AAA"] + weights["BBB"], 0.60)

    def test_bucket_group_cap_limits_related_equity_buckets(self):
        strategy = BigQuantRotationStrategy(
            use_inv_vol_weight=True,
            max_cluster_weight=1.0,
            bucket_map={
                "AAA": "US_EQUITY",
                "BBB": "HK_EQUITY",
                "CCC": "COMMODITY",
            },
            bucket_groups={"RISK_EQUITY": ["US_EQUITY", "HK_EQUITY"]},
            bucket_group_caps={"RISK_EQUITY": 0.70},
        )

        weights = strategy._target_weights(
            {"AAA", "BBB", "CCC"},
            pd.Series({"AAA": 4.0, "BBB": 4.0, "CCC": 1.0}),
        )

        self.assertAlmostEqual(weights["AAA"] + weights["BBB"], 0.70)
        self.assertAlmostEqual(sum(weights.values()), 1.0)

    def test_trend_state_budget_can_relax_strong_bucket(self):
        dates = pd.date_range("2024-01-01", periods=230, freq="B")
        close = pd.DataFrame(
            {
                "QQQ": [100.0 + i * 0.8 for i in range(230)],
                "SPY": [100.0 + i * 0.5 for i in range(230)],
                "IEF": [100.0 + i * 0.02 for i in range(230)],
            },
            index=dates,
        )
        strategy = BigQuantRotationStrategy(
            use_inv_vol_weight=True,
            max_cluster_weight=1.0,
            max_bucket_weight=0.50,
            bucket_map={"QQQ": "US_EQUITY", "SPY": "US_EQUITY", "IEF": "BOND_OR_CASH"},
            use_trend_state_budget=True,
            trend_budget_bucket="US_EQUITY",
            trend_budget_symbols=["QQQ", "SPY"],
            trend_defensive_symbols=["IEF"],
            trend_fast_ma_window=60,
            trend_slow_ma_window=120,
            trend_relative_window=60,
            trend_state_budgets={
                "strong": {"bucket_cap": 0.80},
                "neutral": {"bucket_cap": 0.50},
                "weak": {"bucket_cap": 0.30},
            },
        ).fit(self._market_data_from_close(close))

        weights = strategy._target_weights(
            {"QQQ", "SPY", "IEF"},
            pd.Series({"QQQ": 4.0, "SPY": 4.0, "IEF": 1.0}),
            as_of_date=dates[-1],
        )

        self.assertGreater(weights["QQQ"] + weights["SPY"], 0.50)
        self.assertLessEqual(weights["QQQ"] + weights["SPY"], 0.80 + 1e-12)

    def test_trend_state_budget_tightens_weak_equity_group(self):
        dates = pd.date_range("2024-01-01", periods=230, freq="B")
        close = pd.DataFrame(
            {
                "QQQ": [200.0 - i * 0.4 for i in range(230)],
                "SPY": [180.0 - i * 0.2 for i in range(230)],
                "GLD": [100.0 + i * 0.1 for i in range(230)],
            },
            index=dates,
        )
        strategy = BigQuantRotationStrategy(
            use_inv_vol_weight=True,
            max_cluster_weight=1.0,
            bucket_map={"QQQ": "US_EQUITY", "SPY": "US_EQUITY", "GLD": "COMMODITY"},
            bucket_groups={"RISK_EQUITY": ["US_EQUITY"]},
            use_trend_state_budget=True,
            trend_budget_bucket="US_EQUITY",
            trend_budget_group="RISK_EQUITY",
            trend_budget_symbols=["QQQ", "SPY"],
            trend_defensive_symbols=["GLD"],
            trend_fast_ma_window=60,
            trend_slow_ma_window=120,
            trend_relative_window=60,
            trend_state_budgets={
                "strong": {"bucket_cap": 0.80, "group_cap": 0.90},
                "neutral": {"bucket_cap": 0.60, "group_cap": 0.70},
                "weak": {"bucket_cap": 0.40, "group_cap": 0.35},
            },
        ).fit(self._market_data_from_close(close))

        weights = strategy._target_weights(
            {"QQQ", "SPY", "GLD"},
            pd.Series({"QQQ": 4.0, "SPY": 4.0, "GLD": 1.0}),
            as_of_date=dates[-1],
        )

        self.assertLessEqual(weights["QQQ"] + weights["SPY"], 0.35 + 1e-12)

    def test_entry_confirmation_requires_repeated_top_rank(self):
        strategy = BigQuantRotationStrategy(
            hold_num=1,
            entry_confirm_days=2,
            entry_rank_buffer=0,
        )
        dates = pd.date_range("2024-01-01", periods=2, freq="B")
        strategy._score_panel = pd.DataFrame(
            [{"AAA": 2.0, "BBB": 1.0}, {"AAA": 1.0, "BBB": 2.0}],
            index=dates,
        )

        pool = strategy._entry_pool(dates[-1], pd.Series({"AAA": 1.0, "BBB": 2.0}))

        self.assertEqual(pool, set())

    def test_min_hold_days_blocks_rank_exit(self):
        strategy = BigQuantRotationStrategy(min_hold_days=3)
        strategy.buy_date["AAA"] = pd.Timestamp("2024-01-01")

        self.assertFalse(strategy._can_exit("AAA", pd.Timestamp("2024-01-02")))
        self.assertTrue(strategy._can_exit("AAA", pd.Timestamp("2024-01-04")))

    def test_risk_overlay_can_force_defensive_cash_allocation(self):
        dates = pd.date_range("2024-01-01", periods=130, freq="B")
        close = pd.DataFrame(
            {
                "RISK": [100.0 - i * 0.2 for i in range(130)],
                "DEF": [100.0 + i * 0.1 for i in range(130)],
            },
            index=dates,
        )
        strategy = BigQuantRotationStrategy(
            hold_num=1,
            use_risk_overlay=True,
            risk_symbols=["RISK"],
            defensive_symbols=["DEF"],
            risk_ma_window=20,
            risk_momentum_window=20,
            risk_breadth_threshold=0.5,
            risk_momentum_threshold=0.0,
            defensive_cash_weight=0.25,
            use_inv_vol_weight=False,
        )

        self.assertFalse(strategy._is_risk_on(dates[-1], close))
        filtered = strategy._defensive_score(pd.Series({"RISK": 10.0, "DEF": 1.0}))
        weights = strategy._target_weights(set(filtered.index), pd.Series(1.0, index=["RISK", "DEF"]), filtered)
        weights = {symbol: weight * (1.0 - strategy.defensive_cash_weight) for symbol, weight in weights.items()}

        self.assertEqual(set(weights), {"DEF"})
        self.assertAlmostEqual(weights["DEF"], 0.75)


if __name__ == "__main__":
    unittest.main()
