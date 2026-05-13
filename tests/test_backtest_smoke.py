import unittest

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


if __name__ == "__main__":
    unittest.main()
