import tempfile
import unittest
from pathlib import Path

import pandas as pd

from etf_quant.config.schema import AppConfig, Asset, BacktestConfig, DataConfig, FactorConfig, StrategyConfig
from etf_quant.data.dataset import MarketData
from etf_quant.data.sample import generate_sample_prices
from etf_quant.research.sweep import (
    run_position_cap_sweep,
    run_trend_state_budget_sweep,
    summarize_crisis_windows,
)


class ResearchSweepTests(unittest.TestCase):
    def test_position_cap_sweep_records_each_cap(self):
        assets = [
            Asset(symbol="AAA", name="Alpha", asset_class="us_equity"),
            Asset(symbol="BBB", name="Beta", asset_class="us_equity"),
            Asset(symbol="CCC", name="Gold", asset_class="commodity"),
        ]
        data = MarketData.from_frame(generate_sample_prices(assets, start="2020-01-01", end="2020-12-31"))
        config = AppConfig(
            universe=assets,
            data=DataConfig(source="csv"),
            factors=[FactorConfig(name="bigquant_rotation", params={})],
            strategy=StrategyConfig(
                name="bigquant_rotation",
                params={
                    "hold_num": 2,
                    "specified_etfs": [asset.symbol for asset in assets],
                    "clusters": {"US": ["AAA", "BBB"], "ALT": ["CCC"]},
                    "max_cluster_weight": 1.0,
                },
            ),
            backtest=BacktestConfig(rebalance="D"),
        )

        with tempfile.TemporaryDirectory() as tmp:
            frame = run_position_cap_sweep(config, data, output_dir=Path(tmp), caps=[0.5, 0.8])
            written = Path(tmp) / "position_cap_sweep.csv"
            self.assertTrue(written.exists())

        self.assertEqual(set(frame["max_position_weight"]), {0.5, 0.8})
        self.assertEqual(set(frame["mode"]), {"backtest"})
        self.assertIn("sharpe", frame.columns)

    def test_trend_state_budget_sweep_records_budget_caps(self):
        assets = [
            Asset(symbol="AAA", name="Growth", asset_class="us_equity"),
            Asset(symbol="BBB", name="Broad", asset_class="us_equity"),
            Asset(symbol="CCC", name="Bond", asset_class="bond"),
        ]
        data = MarketData.from_frame(generate_sample_prices(assets, start="2020-01-01", end="2020-12-31"))
        config = AppConfig(
            universe=assets,
            data=DataConfig(source="csv"),
            factors=[FactorConfig(name="bigquant_rotation", params={})],
            strategy=StrategyConfig(
                name="bigquant_rotation",
                params={
                    "hold_num": 2,
                    "specified_etfs": [asset.symbol for asset in assets],
                    "clusters": {"US": ["AAA", "BBB"], "BOND": ["CCC"]},
                    "max_cluster_weight": 1.0,
                    "max_position_weight": 0.6,
                    "bucket_map": {"AAA": "US_EQUITY", "BBB": "US_EQUITY", "CCC": "BOND_OR_CASH"},
                    "bucket_groups": {"RISK_EQUITY": ["US_EQUITY"]},
                    "trend_budget_bucket": "US_EQUITY",
                    "trend_budget_group": "RISK_EQUITY",
                    "trend_budget_symbols": ["AAA", "BBB"],
                    "trend_defensive_symbols": ["CCC"],
                },
            ),
            backtest=BacktestConfig(rebalance="D"),
        )

        with tempfile.TemporaryDirectory() as tmp:
            frame = run_trend_state_budget_sweep(
                config,
                data,
                output_dir=Path(tmp),
                bucket_caps=[0.7],
                group_caps=[0.9],
                weak_group_caps=[0.4],
            )
            written = Path(tmp) / "trend_state_budget_sweep.csv"
            self.assertTrue(written.exists())

        self.assertEqual(set(frame["mode"]), {"backtest"})
        self.assertEqual(frame.loc[0, "strong_bucket_cap"], 0.7)
        self.assertEqual(frame.loc[0, "strong_group_cap"], 0.9)
        self.assertEqual(frame.loc[0, "weak_group_cap"], 0.4)

    def test_crisis_window_summary_captures_exposure_and_holdings(self):
        dates = pd.date_range("2020-02-19", periods=5, freq="B")
        equity = pd.Series([100.0, 90.0, 95.0, 85.0, 110.0], index=dates)
        weights = pd.DataFrame(
            {
                "AAA": [0.6, 0.6, 0.0, 0.0, 0.6],
                "BBB": [0.4, 0.4, 0.5, 0.5, 0.4],
            },
            index=dates,
        )
        turnover = pd.Series([1.0, 0.0, 0.5, 0.0, 0.5], index=dates)

        frame = summarize_crisis_windows(
            equity,
            weights,
            turnover,
            windows=[("sample_stress", "2020-02-19", "2020-02-25")],
        )

        self.assertEqual(frame.loc[0, "window"], "sample_stress")
        self.assertAlmostEqual(frame.loc[0, "window_return"], 0.10)
        self.assertAlmostEqual(frame.loc[0, "max_drawdown"], -0.15)
        self.assertEqual(frame.loc[0, "trade_count"], 3)
        self.assertIn("AAA", frame.loc[0, "top_holdings"])


if __name__ == "__main__":
    unittest.main()
