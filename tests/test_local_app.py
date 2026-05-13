import tempfile
import unittest
from pathlib import Path

from etf_quant.config.schema import AppConfig, DataConfig, StrategyConfig
from etf_quant.app.service import LocalAppPaths, LocalAppService


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

        self.assertEqual(summary["label"], "PYF_ETF轮动")
        self.assertEqual(summary["display_name"], "PYF_ETF轮动")
        self.assertEqual(summary["strategy_name"], "bigquant_rotation")


if __name__ == "__main__":
    unittest.main()
