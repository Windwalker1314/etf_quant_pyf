import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd

from etf_quant.config.schema import Asset
from etf_quant.data.dataset import MarketData
from etf_quant.data.sample import generate_sample_prices
from etf_quant.strategies.rules import (
    EqualWeightStrategy,
    MacroRiskRotationStrategy,
    MomentumRotationStrategy,
    TopAnnualizedReturnStrategy,
)


class BaselineStrategyTests(unittest.TestCase):
    def test_equal_weight_allocates_to_available_symbols(self):
        assets = [
            Asset(symbol="AAA", name="A", asset_class="test"),
            Asset(symbol="BBB", name="B", asset_class="test"),
            Asset(symbol="CCC", name="C", asset_class="test"),
        ]
        data = MarketData.from_frame(generate_sample_prices(assets, start="2020-01-01", end="2020-03-31"))

        weights = EqualWeightStrategy().fit(data).generate_weights(
            pd.Timestamp("2020-03-31"),
            data,
            {},
        )

        self.assertAlmostEqual(weights.sum(), 1.0)
        self.assertTrue((weights == 1.0 / 3).all())

    def test_top_annualized_return_selects_best_two(self):
        frame = pd.DataFrame(
            [
                {"date": "2020-01-01", "symbol": "AAA", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
                {"date": "2020-01-02", "symbol": "AAA", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 1},
                {"date": "2020-01-01", "symbol": "BBB", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
                {"date": "2020-01-02", "symbol": "BBB", "open": 1.5, "high": 1.5, "low": 1.5, "close": 1.5, "volume": 1},
                {"date": "2020-01-01", "symbol": "CCC", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
                {"date": "2020-01-02", "symbol": "CCC", "open": 0.9, "high": 0.9, "low": 0.9, "close": 0.9, "volume": 1},
            ]
        )
        data = MarketData.from_frame(frame)
        strategy = TopAnnualizedReturnStrategy(top_n=2).fit(data)

        self.assertEqual(strategy.selected_symbols, ["AAA", "BBB"])

    def test_momentum_rotation_selects_positive_momentum_assets(self):
        rows = []
        for i, date in enumerate(pd.date_range("2020-01-01", periods=80, freq="B")):
            rows.append(
                {
                    "date": date,
                    "symbol": "AAA",
                    "open": 1 + i * 0.01,
                    "high": 1 + i * 0.01,
                    "low": 1 + i * 0.01,
                    "close": 1 + i * 0.01,
                    "volume": 1,
                }
            )
            rows.append(
                {
                    "date": date,
                    "symbol": "BBB",
                    "open": 1 - i * 0.001,
                    "high": 1 - i * 0.001,
                    "low": 1 - i * 0.001,
                    "close": 1 - i * 0.001,
                    "volume": 1,
                }
            )
        data = MarketData.from_frame(pd.DataFrame(rows))

        weights = MomentumRotationStrategy(
            hold_num=1,
            momentum_windows=[20],
            use_inv_vol_weight=False,
        ).fit(data).generate_weights(pd.Timestamp("2020-04-21"), data, {})

        self.assertEqual(weights.idxmax(), "AAA")
        self.assertAlmostEqual(weights["AAA"], 1.0)

    def test_macro_risk_rotation_can_hold_cash_in_defensive_state(self):
        rows = []
        dates = pd.date_range("2020-01-01", periods=260, freq="B")
        for i, date in enumerate(dates):
            risk_close = max(0.5, 2.0 - i * 0.004)
            bond_close = 1.0 + i * 0.005
            rows.append(
                {
                    "date": date,
                    "symbol": "RISK",
                    "open": risk_close,
                    "high": risk_close,
                    "low": risk_close,
                    "close": risk_close,
                    "volume": 1,
                }
            )
            rows.append(
                {
                    "date": date,
                    "symbol": "BOND",
                    "open": bond_close,
                    "high": bond_close,
                    "low": bond_close,
                    "close": bond_close,
                    "volume": 1,
                }
            )
        data = MarketData.from_frame(pd.DataFrame(rows))

        weights = MacroRiskRotationStrategy(
            risk_symbols=["RISK"],
            defensive_symbols=["BOND"],
            momentum_windows=[20],
            risk_ma_window=60,
            breadth_window=60,
            cash_weight_when_defensive=0.25,
            safe_asset="BOND",
            use_inv_vol_weight=False,
        ).fit(data).generate_weights(dates[-1], data, {})

        self.assertAlmostEqual(weights["BOND"], 0.75)
        self.assertAlmostEqual(weights.sum(), 0.75)

    def test_macro_risk_rotation_uses_macro_trend_filter(self):
        rows = []
        dates = pd.date_range("2020-01-01", periods=260, freq="B")
        for i, date in enumerate(dates):
            risk_close = 1.0 + i * 0.01
            bond_close = 1.0 + i * 0.0005
            rows.append(
                {
                    "date": date,
                    "symbol": "RISK",
                    "open": risk_close,
                    "high": risk_close,
                    "low": risk_close,
                    "close": risk_close,
                    "volume": 1,
                }
            )
            rows.append(
                {
                    "date": date,
                    "symbol": "BOND",
                    "open": bond_close,
                    "high": bond_close,
                    "low": bond_close,
                    "close": bond_close,
                    "volume": 1,
                }
            )
        data = MarketData.from_frame(pd.DataFrame(rows))

        with TemporaryDirectory() as tmpdir:
            macro_path = Path(tmpdir) / "macro.csv"
            macro_values = [1.0] * 180 + [1.0 - i * 0.003 for i in range(80)]
            macro = pd.DataFrame(
                {
                    "date": dates,
                    "credit_risk_ratio": macro_values,
                }
            )
            macro.to_csv(macro_path, index=False)

            weights = MacroRiskRotationStrategy(
                risk_symbols=["RISK"],
                defensive_symbols=["BOND"],
                momentum_windows=[20],
                risk_ma_window=60,
                breadth_window=60,
                use_inv_vol_weight=False,
                macro_data_path=str(macro_path),
                macro_lag_days=0,
                use_macro_filter=True,
                macro_trend_col="credit_risk_ratio",
                macro_trend_ma_window=60,
                macro_trend_min_gap=-0.02,
            ).fit(data).generate_weights(dates[-1], data, {})

        self.assertAlmostEqual(weights["BOND"], 1.0)
        self.assertAlmostEqual(weights["RISK"], 0.0)


if __name__ == "__main__":
    unittest.main()
