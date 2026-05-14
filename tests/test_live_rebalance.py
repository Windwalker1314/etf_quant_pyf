import tempfile
import unittest
from pathlib import Path

import pandas as pd

from etf_quant.config.schema import AppConfig, Asset, BacktestConfig, DataConfig, FactorConfig, StrategyConfig
from etf_quant.data.dataset import MarketData
from etf_quant.data.sample import generate_sample_prices
from etf_quant.live.rebalance import build_live_rebalance_plan, load_positions


class LiveRebalanceTests(unittest.TestCase):
    def test_load_positions_reads_cash_row_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "positions.csv"
            path.write_text("symbol,shares,cash\nAAA,100,\nCASH,0,12345\n", encoding="utf-8")

            shares, cash = load_positions(path, ["AAA"])

        self.assertEqual(shares["AAA"], 100)
        self.assertEqual(cash, 12345)

    def test_live_plan_outputs_trade_shares(self):
        assets = [
            Asset(symbol="510300.SH", name="CSI 300", asset_class="cn_equity"),
            Asset(symbol="159915.SZ", name="ChiNext", asset_class="cn_equity"),
            Asset(symbol="518880.SH", name="Gold", asset_class="commodity"),
        ]
        data = MarketData.from_frame(generate_sample_prices(assets, start="2020-01-01", end="2022-12-31"))
        config = AppConfig(
            universe=assets,
            data=DataConfig(source="csv"),
            factors=[FactorConfig(name="bigquant_rotation", params={})],
            strategy=StrategyConfig(
                name="bigquant_rotation",
                params={
                    "hold_num": 2,
                    "specified_etfs": [asset.symbol for asset in assets],
                    "clusters": {"A": ["510300.SH", "159915.SZ"], "ALT": ["518880.SH"]},
                },
            ),
            backtest=BacktestConfig(rebalance="D"),
        )

        plan = build_live_rebalance_plan(config, data, cash=100000, lot_size=100)

        self.assertIn("trade_shares", plan.plan.columns)
        self.assertGreaterEqual(plan.portfolio_value, 100000)
        self.assertTrue((plan.plan["trade_shares"] % 100 == 0).all())

    def test_live_plan_accepts_in_memory_current_shares(self):
        assets = [
            Asset("AAA", "AAA", "equity"),
            Asset("BBB", "BBB", "equity"),
        ]
        data = MarketData.from_frame(generate_sample_prices(assets, start="2020-01-01", end="2022-12-31"))
        config = AppConfig(
            universe=assets,
            data=DataConfig(source="csv"),
            factors=[],
            strategy=StrategyConfig(name="equal_weight"),
            backtest=BacktestConfig(rebalance="D"),
        )
        shares = pd.Series({"AAA": 100.0, "BBB": 0.0})

        plan = build_live_rebalance_plan(config, data, current_shares=shares, cash=10000, lot_size=1)

        self.assertEqual(float(plan.plan.loc[plan.plan["symbol"] == "AAA", "current_shares"].iloc[0]), 100.0)
        self.assertIn("estimated_shares", plan.plan.columns)


if __name__ == "__main__":
    unittest.main()
