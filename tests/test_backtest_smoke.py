import unittest

import pandas as pd

from etf_quant.backtest.engine import BacktestEngine
from etf_quant.config.schema import Asset, BacktestConfig, FactorConfig, StrategyConfig
from etf_quant.data.dataset import MarketData
from etf_quant.data.sample import generate_sample_prices
from etf_quant.factors.library import compute_factor_panel
from etf_quant.strategies.registry import build_strategy


class BacktestSmokeTests(unittest.TestCase):
    def test_backtest_runs_on_sample_data(self):
        assets = [
            Asset(symbol="AAA", name="A", asset_class="test"),
            Asset(symbol="BBB", name="B", asset_class="test"),
            Asset(symbol="CCC", name="C", asset_class="test"),
        ]
        data = MarketData.from_frame(
            generate_sample_prices(assets, start="2020-01-01", end="2021-12-31")
        )
        factors = [
            FactorConfig(name="momentum", params={"window": 20}),
            FactorConfig(name="volatility", params={"window": 20}),
        ]
        strategy = build_strategy(
            StrategyConfig(
                name="multi_factor_rule",
                params={"top_n": 2, "factor_weights": {"momentum": 1.0, "volatility": -0.5}},
            )
        ).fit(data)

        result = BacktestEngine(BacktestConfig(rebalance="M")).run(data, factors, strategy)

        self.assertFalse(result.equity_curve.empty)
        self.assertGreater(result.equity_curve.iloc[-1], 0)
        self.assertIn("sharpe", result.metrics)
        self.assertIn("annualized_turnover", result.metrics)
        self.assertIn("avg_active_positions", result.metrics)

    def test_backtest_accepts_precomputed_factor_data(self):
        assets = [
            Asset(symbol="AAA", name="A", asset_class="test"),
            Asset(symbol="BBB", name="B", asset_class="test"),
        ]
        data = MarketData.from_frame(
            generate_sample_prices(assets, start="2020-01-01", end="2020-12-31")
        )
        factors = [FactorConfig(name="momentum", params={"window": 20})]
        strategy = build_strategy(
            StrategyConfig(name="multi_factor_rule", params={"top_n": 1, "factor_weights": {"momentum": 1.0}})
        ).fit(data)
        factor_data = compute_factor_panel(data, factors)

        result = BacktestEngine(BacktestConfig(rebalance="M")).run(
            data,
            factors,
            strategy,
            factor_data=factor_data,
        )

        self.assertFalse(result.equity_curve.empty)

    def test_next_open_falls_back_when_ohlc_is_adjusted_inconsistently(self):
        frame = pd.DataFrame(
            [
                {"date": "2020-01-01", "symbol": "AAA", "open": 100.0, "high": 101.0, "low": 99.0, "close": 50.0, "volume": 1},
                {"date": "2020-01-02", "symbol": "AAA", "open": 110.0, "high": 111.0, "low": 109.0, "close": 55.0, "volume": 1},
                {"date": "2020-01-03", "symbol": "AAA", "open": 120.0, "high": 121.0, "low": 119.0, "close": 60.0, "volume": 1},
            ]
        )
        data = MarketData.from_frame(frame)
        strategy = build_strategy(StrategyConfig(name="equal_weight", params={})).fit(data)

        result = BacktestEngine(
            BacktestConfig(
                rebalance="D",
                execution="next_open",
                initial_cash=100.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            )
        ).run(
            data,
            [],
            strategy,
        )

        self.assertGreater(data.ohlc_anomaly_ratio(), 0.01)
        self.assertAlmostEqual(result.daily_returns.iloc[1], 0.10)

    def test_market_data_drops_export_index_columns(self):
        frame = pd.DataFrame(
            [
                {
                    "Unnamed: 0": 0,
                    "date": "2020-01-01",
                    "symbol": "AAA",
                    "open": 1.0,
                    "high": 1.1,
                    "low": 0.9,
                    "close": 1.0,
                    "volume": 1,
                }
            ]
        )
        data = MarketData.from_frame(frame)

        self.assertNotIn("Unnamed: 0", data.prices.columns)


if __name__ == "__main__":
    unittest.main()
