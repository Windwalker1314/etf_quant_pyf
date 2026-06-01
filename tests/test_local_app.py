import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from etf_quant.config.schema import AppConfig, Asset, BacktestConfig, DataConfig, StrategyConfig
from etf_quant.app.service import APP_STRATEGY_CONFIGS, LocalAppPaths, LocalAppService
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

    def test_app_strategy_allowlist_only_contains_best_long_and_short_configs(self):
        self.assertEqual(
            APP_STRATEGY_CONFIGS,
            [
                "configs/global_etf_position_cap_yahoo.yaml",
                "configs/bigquant_rotation_hybrid_position_cap.yaml",
            ],
        )

    def test_best_strategy_display_names_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = LocalAppService(root=Path(tmp))
            long_summary = service._strategy_summary(
                Path(tmp) / "configs/global_etf_position_cap_yahoo.yaml",
                AppConfig(
                    universe=[],
                    data=DataConfig(source="yahoo", start="2006-02-06", end="2026-05-11"),
                    factors=[],
                    strategy=StrategyConfig(name="bigquant_rotation"),
                ),
            )
            short_summary = service._strategy_summary(
                Path(tmp) / "configs/bigquant_rotation_hybrid_position_cap.yaml",
                AppConfig(
                    universe=[],
                    data=DataConfig(source="csv", start="2020-01-01", end="2026-05-11"),
                    factors=[],
                    strategy=StrategyConfig(name="bigquant_rotation"),
                ),
            )

        self.assertEqual(long_summary["label"], "长线Sharpe最优：全球ETF轮动")
        self.assertEqual(short_summary["label"], "短线Sharpe最优：国内Hybrid轮动")

    def test_strategy_summary_prefers_actual_cached_date_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            price_path = root / "prices.csv"
            price_path.write_text(
                "\n".join(
                    [
                        "date,symbol,open,high,low,close,volume",
                        "2026-05-10,AAA,1,1,1,1,1",
                        "2026-05-14,AAA,2,2,2,2,1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            service = LocalAppService(root=root)
            summary = service._strategy_summary(
                root / "strategy.yaml",
                AppConfig(
                    universe=[],
                    data=DataConfig(source="csv", path=price_path, start="2026-01-01", end="2026-05-11"),
                    factors=[],
                    strategy=StrategyConfig(name="equal_weight"),
                ),
            )

        self.assertEqual(summary["date_range"], "2026-05-10 - 2026-05-14")
        self.assertEqual(summary["configured_date_range"], "2026-01-01 - 2026-05-11")
        self.assertEqual(summary["actual_date_range"], "2026-05-10 - 2026-05-14")

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
            paths = LocalAppPaths(
                root=root,
                positions_path=Path("positions.csv"),
                state_path=Path("state.json"),
                performance_log_path=Path("performance.csv"),
            )
            service = LocalAppService(root=root, paths=paths)

            plan = service.generate_plan({"config_path": str(config_path), "refresh_data": True, "lot_size": 1})

            saved_positions = positions_path.read_text(encoding="utf-8")

        self.assertEqual(plan["as_of_date"], "2026-05-11")
        self.assertEqual(plan["latest_data_date"], "2026-05-11")
        self.assertFalse(plan["refresh_data"])
        self.assertEqual(plan["performance"]["record_count"], 1)
        self.assertEqual(plan["performance"]["latest"]["date"], "2026-05-11")
        self.assertEqual(plan["performance"]["latest"]["daily_return"], 0.0)
        self.assertEqual(plan["targets"][0]["name"], "Alpha")
        self.assertEqual(plan["orders"][0]["name"], "Alpha")
        self.assertIn("AAA,0,", saved_positions)
        self.assertEqual(plan["projected_positions"]["holdings"][0]["shares"], 500.0)
        self.assertEqual(plan["projected_positions"]["cash"], 0.0)

    def test_generate_plan_updates_performance_log_and_bootstrap_returns_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "strategy.yaml"
            price_path = root / "prices.csv"
            positions_path = root / "positions.csv"
            state_path = root / "state.json"
            performance_path = root / "performance.csv"
            price_path.write_text(
                "\n".join(
                    [
                        "date,symbol,open,high,low,close,volume",
                        "2026-05-10,AAA,10,10,10,10,1",
                        "2026-05-11,AAA,11,11,11,11,1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            positions_path.write_text("symbol,shares,cash\nAAA,100,\nCASH,0,0\n", encoding="utf-8")
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
output_dir: outputs/app-test
""",
                encoding="utf-8",
            )
            paths = LocalAppPaths(
                root=root,
                positions_path=Path("positions.csv"),
                state_path=Path("state.json"),
                performance_log_path=Path("performance.csv"),
                strategy_glob="strategy.yaml",
            )
            service = LocalAppService(root=root, paths=paths)

            first = service.generate_plan({"config_path": str(config_path), "refresh_data": False, "lot_size": 1})
            second = service.generate_plan({"config_path": str(config_path), "refresh_data": False, "lot_size": 1})
            bootstrap = service.bootstrap()
            performance_exists = performance_path.exists()
            saved_state = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertTrue(performance_exists)
        self.assertEqual(first["performance"]["record_count"], 1)
        self.assertEqual(second["performance"]["record_count"], 1)
        self.assertEqual(bootstrap["performance"]["record_count"], 1)
        self.assertEqual(bootstrap["last_plan"]["as_of_date"], "2026-05-11")
        self.assertEqual(bootstrap["last_plan"]["portfolio_value"], 1100.0)
        self.assertEqual(bootstrap["last_plan"]["trade_count"], second["trade_count"])
        self.assertEqual(bootstrap["performance"]["latest"]["portfolio_value"], 1100.0)
        self.assertEqual(Path(saved_state["selected_config"]).resolve(), config_path.resolve())

    def test_performance_returns_are_calculated_per_strategy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            performance_path = root / "performance.csv"
            performance_path.write_text(
                "\n".join(
                    [
                        "date,config_path,strategy_label,portfolio_value,cash,latest_data_date,refresh_data,recorded_at",
                        "2026-05-10,a.yaml,A,1000,0,2026-05-10,False,2026-05-10T00:00:00+00:00",
                        "2026-05-11,a.yaml,A,1100,0,2026-05-11,False,2026-05-11T00:00:00+00:00",
                        "2026-05-11,b.yaml,B,2000,0,2026-05-11,False,2026-05-11T00:00:00+00:00",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            paths = LocalAppPaths(
                root=root,
                positions_path=Path("positions.csv"),
                state_path=Path("state.json"),
                performance_log_path=Path("performance.csv"),
            )
            service = LocalAppService(root=root, paths=paths)

            perf = service.get_performance("a.yaml")

        self.assertEqual(perf["record_count"], 2)
        self.assertAlmostEqual(perf["latest"]["daily_return"], 0.1)
        self.assertAlmostEqual(perf["latest"]["cumulative_return"], 0.1)

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
