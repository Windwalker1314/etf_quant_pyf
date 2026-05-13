from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from etf_quant.config.loader import load_config
from etf_quant.config.schema import AppConfig
from etf_quant.data.sources import download_market_data, load_market_data
from etf_quant.io import ensure_dir, write_frame
from etf_quant.live.rebalance import build_live_rebalance_plan, format_live_plan_markdown, load_positions


DEFAULT_STRATEGY_GLOB = "configs/*hybrid*.yaml"
DEFAULT_SELECTED_CONFIG = "configs/bigquant_rotation_hybrid_candidate_turnover.yaml"
DEFAULT_POSITIONS_PATH = Path("data/live/positions.csv")
DEFAULT_STATE_PATH = Path("data/live/app_state.json")
STRATEGY_DISPLAY_NAMES = {
    "bigquant_rotation": "PYF_ETF轮动",
}


@dataclass(frozen=True)
class LocalAppPaths:
    root: Path
    positions_path: Path = DEFAULT_POSITIONS_PATH
    state_path: Path = DEFAULT_STATE_PATH
    strategy_glob: str = DEFAULT_STRATEGY_GLOB

    def resolve(self, path: str | Path) -> Path:
        value = Path(path)
        return value if value.is_absolute() else self.root / value

    @property
    def positions(self) -> Path:
        return self.resolve(self.positions_path)

    @property
    def state(self) -> Path:
        return self.resolve(self.state_path)


class LocalAppService:
    def __init__(self, root: str | Path | None = None, paths: LocalAppPaths | None = None) -> None:
        repo_root = Path(root or Path.cwd()).resolve()
        self.paths = paths or LocalAppPaths(root=repo_root)

    def bootstrap(self) -> dict[str, Any]:
        strategies = self.list_strategies()
        state = self.load_state()
        selected = self._selected_config_from_state(state, strategies)
        return {
            "strategies": strategies,
            "selected_config": selected,
            "positions": self.get_positions(selected),
            "settings": {
                "lot_size": int(state.get("lot_size", 100)),
                "min_trade_value": float(state.get("min_trade_value", 0.0)),
                "refresh_data": bool(state.get("refresh_data", True)),
            },
        }

    def list_strategies(self) -> list[dict[str, Any]]:
        configs = sorted(self.paths.root.glob(self.paths.strategy_glob))
        if not configs:
            configs = sorted((self.paths.root / "configs").glob("*.yaml"))
        preferred = self.paths.resolve(DEFAULT_SELECTED_CONFIG).resolve()
        configs = sorted(configs, key=lambda path: (path.resolve() != preferred, path.name))
        strategies = []
        for config_path in configs:
            try:
                config = load_config(config_path)
            except Exception:
                continue
            strategies.append(self._strategy_summary(config_path, config))
        return strategies

    def get_positions(self, config_path: str | Path | None = None) -> dict[str, Any]:
        symbols = self._symbols_for_config(config_path)
        names = self._names_for_config(config_path)
        shares, cash = load_positions(self.paths.positions if self.paths.positions.exists() else None, symbols)
        holdings = []
        for symbol in symbols:
            holdings.append(
                {
                    "symbol": symbol,
                    "name": names.get(symbol, ""),
                    "shares": float(shares.get(symbol, 0.0)),
                }
            )
        return {"cash": float(cash), "holdings": holdings, "path": str(self.paths.positions)}

    def save_positions(self, payload: dict[str, Any]) -> dict[str, Any]:
        holdings = payload.get("holdings", [])
        cash = float(payload.get("cash") or 0.0)
        ensure_dir(self.paths.positions.parent)
        with self.paths.positions.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["symbol", "shares", "cash"])
            writer.writeheader()
            for item in holdings:
                symbol = str(item.get("symbol", "")).strip()
                if not symbol:
                    continue
                writer.writerow({"symbol": symbol, "shares": float(item.get("shares") or 0.0), "cash": ""})
            writer.writerow({"symbol": "CASH", "shares": 0, "cash": cash})
        return self.get_positions(payload.get("config_path"))

    def save_state(self, patch: dict[str, Any]) -> dict[str, Any]:
        state = self.load_state()
        state.update({key: value for key, value in patch.items() if value is not None})
        ensure_dir(self.paths.state.parent)
        self.paths.state.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state

    def load_state(self) -> dict[str, Any]:
        if not self.paths.state.exists():
            return {}
        try:
            return json.loads(self.paths.state.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def generate_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        config_path = self._resolve_config(payload.get("config_path"))
        lot_size = int(payload.get("lot_size") or 100)
        min_trade_value = float(payload.get("min_trade_value") or 0.0)
        refresh_data = bool(payload.get("refresh_data"))
        if "holdings" in payload or "cash" in payload:
            self.save_positions({**payload, "config_path": str(config_path)})
        self.save_state(
            {
                "selected_config": self._display_path(config_path),
                "lot_size": lot_size,
                "min_trade_value": min_trade_value,
                "refresh_data": refresh_data,
            }
        )

        config = load_config(config_path)
        if refresh_data:
            market_data = download_market_data(config.data, config.universe)
            if config.data.path is None:
                raise ValueError("刷新行情需要在策略配置里设置 data.path")
            write_frame(market_data.prices, config.data.path)
        else:
            market_data = load_market_data(config.data)

        plan = build_live_rebalance_plan(
            config,
            market_data,
            positions_path=self.paths.positions,
            lot_size=lot_size,
            min_trade_value=min_trade_value,
        )
        output_dir = ensure_dir(config.output_dir / "app")
        write_frame(plan.plan, output_dir / "live_rebalance_plan.csv")
        (output_dir / "live_rebalance_plan.md").write_text(format_live_plan_markdown(plan), encoding="utf-8")

        return {
            "strategy": self._strategy_summary(config_path, config),
            "as_of_date": plan.as_of_date.date().isoformat(),
            "portfolio_value": plan.portfolio_value,
            "cash": plan.cash,
            "trade_count": int((plan.plan["side"] != "HOLD").sum()),
            "orders": self._records(plan.plan[plan.plan["side"] != "HOLD"].copy()),
            "targets": self._records(plan.plan.sort_values("target_weight", ascending=False).copy()),
            "output_dir": str(output_dir),
            "markdown": format_live_plan_markdown(plan),
        }

    def _symbols_for_config(self, config_path: str | Path | None) -> list[str]:
        if config_path is None:
            return []
        try:
            return [asset.symbol for asset in load_config(self._resolve_config(config_path)).universe]
        except Exception:
            return []

    def _names_for_config(self, config_path: str | Path | None) -> dict[str, str]:
        if config_path is None:
            return {}
        try:
            return {asset.symbol: asset.name for asset in load_config(self._resolve_config(config_path)).universe}
        except Exception:
            return {}

    def _resolve_config(self, value: str | Path | None) -> Path:
        if value:
            path = Path(value)
            if not path.is_absolute():
                path = self.paths.root / path
            return path.resolve()
        state = self.load_state()
        if state.get("selected_config"):
            return self._resolve_config(state["selected_config"])
        strategies = self.list_strategies()
        if not strategies:
            raise ValueError("没有找到可用策略配置")
        return self._resolve_config(strategies[0]["path"])

    def _selected_config_from_state(self, state: dict[str, Any], strategies: list[dict[str, Any]]) -> str | None:
        if not strategies:
            return None
        available = {strategy["path"] for strategy in strategies}
        selected = state.get("selected_config")
        if selected in available:
            return selected
        if DEFAULT_SELECTED_CONFIG in available:
            return DEFAULT_SELECTED_CONFIG
        return strategies[0]["path"]

    def _strategy_summary(self, config_path: Path, config: AppConfig) -> dict[str, Any]:
        display_name = STRATEGY_DISPLAY_NAMES.get(config.strategy.name, config.strategy.name)
        return {
            "path": self._display_path(config_path),
            "label": display_name,
            "strategy_name": config.strategy.name,
            "display_name": display_name,
            "data_source": config.data.source,
            "universe_size": len(config.universe),
            "output_dir": str(config.output_dir),
        }

    def _display_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.paths.root))
        except ValueError:
            return str(path.resolve())

    @staticmethod
    def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
        clean = frame.replace([float("inf"), float("-inf")], pd.NA).where(pd.notna(frame), None)
        return clean.to_dict(orient="records")
