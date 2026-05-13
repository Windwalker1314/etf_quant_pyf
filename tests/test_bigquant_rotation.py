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
            pd.Series(1.0, index=["AAA", "BBB", "CCC"]),
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


if __name__ == "__main__":
    unittest.main()
