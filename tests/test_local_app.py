import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from etf_quant.config.schema import AppConfig, Asset, BacktestConfig, DataConfig, StrategyConfig
from etf_quant.app.service import LocalAppPaths, LocalAppService
from etf_quant.data.dataset import MarketData


class LocalAppServiceTests(unittest.TestCase):
    def test_save_positions_round_trips_cash_and_holdings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = LocalAppPaths(root=root, positions_path=Path("positions.csv"), state_path=Path("state.json"))
            service = LocalAppService(root=root, paths=paths)

            service.save_positions(
                {
                    "cash": 1234.5,
                    "holdings": [
                        {"symbol": "AAA", "shares": 100},
                        {"symbol": "BBB", "shares": 200},
                    ],
                }
            )

            positions = service.get_positions()

        self.assertEqual(positions["cash"], 1234.5)
        self.assertEqual(positions["path"], str(root / "positions.csv"))

    def test_state_patch_preserves_existing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = LocalAppPaths(root=root, positions_path=Path("positions.csv"), state_path=Path("state.json"))
            service = LocalAppService(root=root, paths=paths)

            service.save_state({"selected_config": "configs/live/a.yaml", "lot_size": 100})
            state = service.save_state({"lot_size": 200})

        self.assertEqual(state["selected_config"], "configs/live/a.yaml")
        self.assertEqual(state["lot_size"], 200)

    def test_bigquant_rotation_uses_personal_display_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = LocalAppService(root=Path(tmp))
            summary = service._strategy_summary(
                Path(tmp) / "configs/live/bigquant_rotation_live_akshare.yaml",
                AppConfig(
                    universe=[],
                    data=DataConfig(source="akshare"),
                    factors=[],
                    strategy=StrategyConfig(name="bigquant_rotation"),
                ),
            )

        self.assertEqual(summary["label"], "PYF ETF轮动")
        self.assertEqual(summary["display_name"], "PYF ETF轮动")
        self.assertEqual(summary["strategy_name"], "bigquant_rotation")

    def test_config_display_name_overrides_strategy_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = LocalAppService(root=Path(tmp))
            summary = service._strategy_summary(
                Path(tmp) / "configs/pyf_global_etf_rotation_yahoo.yaml",
                AppConfig(
                    universe=[],
                    data=DataConfig(source="yahoo", start="2006-02-06", end="2026-05-11"),
                    factors=[],
                    strategy=StrategyConfig(name="bigquant_rotation"),
                ),
            )

        self.assertEqual(summary["label"], "PYF全球ETF轮动")
        self.assertEqual(summary["date_range"], "2006-02-06 - 2026-05-11")

    def test_regular_csv_strategy_refresh_request_uses_cached_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "strategy.yaml"
            price_path = root / "prices.csv"
            positions_path = root / "positions.csv"
            price_path.write_text(
                "\n".join(
                    [
                        "date,symbol,open,high,low,close,volume",
                        "2026-05-10,AAA,1,1,1,1,1",
                        "2026-05-11,AAA,2,2,2,2,1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            positions_path.write_text("symbol,shares,cash\nAAA,0,\nCASH,0,1000\n", encoding="utf-8")
            config_path.write_text(
                """
universe:
  - symbol: AAA
    name: Alpha
    asset_class: test
data:
  source: csv
  path: prices.csv
  start: "2026-01-01"
  end: "2026-05-11"
strategy:
  name: equal_weight
backtest:
  initial_cash: 1000
factors: []
""",
                encoding="utf-8",
            )
            paths = LocalAppPaths(root=root, positions_path=Path("positions.csv"), state_path=Path("state.json"))
            service = LocalAppService(root=root, paths=paths)

            plan = service.generate_plan({"config_path": str(config_path), "refresh_data": True, "lot_size": 1})

            saved_positions = positions_path.read_text(encoding="utf-8")

        self.assertEqual(plan["as_of_date"], "2026-05-11")
        self.assertEqual(plan["latest_data_date"], "2026-05-11")
        self.assertFalse(plan["refresh_data"])
        self.assertIn("AAA,0,", saved_positions)
        self.assertEqual(plan["projected_positions"]["holdings"][0]["shares"], 500.0)
        self.assertEqual(plan["projected_positions"]["cash"], 0.0)

    def test_hybrid_strategy_refresh_updates_yahoo_and_akshare_legs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "strategy.yaml"
            price_path = root / "bigquant_hybrid_prices.csv"
            positions_path = root / "positions.csv"
            price_path.write_text(
                "\n".join(
                    [
                        "date,symbol,open,high,low,close,volume",
                        "2026-05-11,160723.SZ,1,1,1,1,1",
                        "2026-05-11,513100.SH,2,2,2,2,1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            positions_path.write_text("symbol,shares,cash\n160723.SZ,0,\n513100.SH,0,\nCASH,0,1000\n", encoding="utf-8")
            config_path.write_text(
                """
universe:
  - symbol: 160723.SZ
    name: Oil
    asset_class: commodity
  - symbol: 513100.SH
    name: Nasdaq
    asset_class: us_equity
data:
  source: csv
  path: bigquant_hybrid_prices.csv
  start: "2026-01-01"
  end: "2026-05-11"
strategy:
  name: equal_weight
backtest:
  initial_cash: 1000
factors: []
""",
                encoding="utf-8",
            )
            yahoo = MarketData.from_frame(
                pd.DataFrame(
                    [
                        {
                            "date": "2026-05-14",
                            "symbol": "513100.SH",
                            "open": 3,
                            "high": 3,
                            "low": 3,
                            "close": 3,
                            "volume": 1,
                        }
                    ]
                )
            )
            akshare = MarketData.from_frame(
                pd.DataFrame(
                    [
                        {
                            "date": "2026-05-14",
                            "symbol": "160723.SZ",
                            "open": 4,
                            "high": 4,
                            "low": 4,
                            "close": 4,
                            "volume": 1,
                        }
                    ]
                )
            )

            def fake_download(data_config, universe):
                symbols = {asset.symbol for asset in universe}
                if data_config.source == "yahoo":
                    self.assertEqual(symbols, {"513100.SH"})
                    self.assertIsNone(data_config.end)
                    self.assertEqual(data_config.start, "2026-05-04")
                    return yahoo
                if data_config.source == "akshare":
                    self.assertEqual(symbols, {"160723.SZ"})
                    self.assertIsNone(data_config.end)
                    self.assertEqual(data_config.start, "2026-05-04")
                    return akshare
                raise AssertionError(data_config.source)

            paths = LocalAppPaths(root=root, positions_path=Path("positions.csv"), state_path=Path("state.json"))
            service = LocalAppService(root=root, paths=paths)

            with patch("etf_quant.app.service.download_market_data", side_effect=fake_download) as download:
                plan = service.generate_plan({"config_path": str(config_path), "refresh_data": True, "lot_size": 1})

        self.assertEqual(download.call_count, 2)
        self.assertEqual(plan["as_of_date"], "2026-05-14")
        self.assertEqual(plan["latest_data_date"], "2026-05-14")
        self.assertTrue(plan["refresh_data"])

    def test_remote_incremental_refresh_ignores_stale_config_end_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cached_path = root / "prices.csv"
            cached_path.write_text("date,symbol,open,high,low,close,volume\n2026-05-11,AAA,1,1,1,1,1\n", encoding="utf-8")
            service = LocalAppService(root=root)
            config = AppConfig(
                universe=[Asset(symbol="AAA", name="Alpha", asset_class="test")],
                data=DataConfig(source="akshare", path=cached_path, start="2020-01-01", end="2026-05-11"),
                factors=[],
                strategy=StrategyConfig(name="bigquant_rotation"),
                backtest=BacktestConfig(),
            )
            fresh = MarketData.from_frame(
                pd.DataFrame(
                    [
                        {"date": "2026-05-11", "symbol": "AAA", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2},
                        {"date": "2026-05-14", "symbol": "AAA", "open": 3, "high": 3, "low": 3, "close": 3, "volume": 3},
                    ]
                )
            )

            with patch("etf_quant.app.service.download_market_data", return_value=fresh) as download:
                refreshed = service._refresh_market_data(config)

        requested_config = download.call_args.args[0]
        self.assertIsNone(requested_config.end)
        self.assertEqual(requested_config.start, "2026-05-04")
        self.assertEqual(refreshed.prices["date"].max().date().isoformat(), "2026-05-14")
        self.assertEqual(float(refreshed.prices.loc[refreshed.prices["date"] == pd.Timestamp("2026-05-11"), "close"].iloc[0]), 2.0)


if __name__ == "__main__":
    unittest.main()
