from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from etf_quant.config.loader import load_config
from etf_quant.config.schema import AppConfig, DataConfig
from etf_quant.data.dataset import MarketData
from etf_quant.data.sources import download_market_data, load_market_data
from etf_quant.io import ensure_dir, write_frame
from etf_quant.live.rebalance import build_live_rebalance_plan, format_live_plan_markdown, load_positions


DEFAULT_STRATEGY_GLOB = "configs/*.yaml"
DEFAULT_SELECTED_CONFIG = "configs/bigquant_rotation_hybrid_candidate_take_profit.yaml"
DEFAULT_POSITIONS_PATH = Path("data/live/positions.csv")
DEFAULT_STATE_PATH = Path("data/live/app_state.json")
STRATEGY_DISPLAY_NAMES = {
    "bigquant_rotation": "PYF ETF轮动",
}
CONFIG_DISPLAY_NAMES = {
    "configs/pyf_global_etf_rotation_yahoo.yaml": "PYF全球ETF轮动",
    "configs/bigquant_rotation_hybrid_candidate_take_profit.yaml": "PYF国内ETF止盈轮动",
    "configs/bigquant_rotation_hybrid_candidate_turnover.yaml": "PYF国内ETF换手优化",
}
APP_STRATEGY_CONFIGS = [
    "configs/bigquant_rotation_hybrid_candidate_take_profit.yaml",
    "configs/bigquant_rotation_hybrid_candidate_turnover.yaml",
    "configs/pyf_global_etf_rotation_yahoo.yaml",
    "configs/live/bigquant_rotation_live_akshare.yaml",
]
REMOTE_DATA_SOURCES = {"akshare", "tushare", "yahoo"}
INCREMENTAL_REFRESH_OVERLAP_DAYS = 7
HYBRID_PRICE_FILE = "bigquant_hybrid_prices.csv"
HYBRID_AKSHARE_SYMBOLS = {"160723.SZ"}


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
            "backtest": self.get_backtest(selected),
            "settings": {
                "lot_size": int(state.get("lot_size", 100)),
                "min_trade_value": float(state.get("min_trade_value", 0.0)),
                "refresh_data": bool(state.get("refresh_data", True)),
            },
        }

    def list_strategies(self) -> list[dict[str, Any]]:
        configs = [self.paths.resolve(path) for path in APP_STRATEGY_CONFIGS if self.paths.resolve(path).exists()]
        if not configs:
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

    def get_backtest(self, config_path: str | Path | None = None, years: int = 5) -> dict[str, Any]:
        if config_path is None:
            return {"metrics": {}, "curve": [], "years": years}
        try:
            config_path = self._resolve_config(config_path)
            config = load_config(config_path)
        except Exception:
            return {"metrics": {}, "curve": [], "years": years}

        metrics = self._load_metrics(config.output_dir / "metrics.yaml")
        curve = self._load_equity_curve(config.output_dir / "equity_curve.csv", years=years)
        return {
            "metrics": metrics,
            "curve": curve,
            "years": years,
            "output_dir": str(config.output_dir),
        }

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
        config = load_config(config_path)
        refresh_data = bool(payload.get("refresh_data", True)) and self._can_refresh_data(config)
        self.save_state(
            {
                "selected_config": self._display_path(config_path),
                "lot_size": lot_size,
                "min_trade_value": min_trade_value,
                "refresh_data": refresh_data,
            }
        )

        if refresh_data:
            market_data = (
                self._refresh_hybrid_market_data(config)
                if self._is_hybrid_data_config(config)
                else self._refresh_market_data(config)
            )
            if config.data.path is None:
                raise ValueError("刷新行情需要在策略配置里设置 data.path")
            write_frame(market_data.prices, config.data.path)
        else:
            market_data = load_market_data(config.data)

        latest_data_date = self._latest_data_date(market_data)
        plan = build_live_rebalance_plan(
            config,
            market_data,
            positions_path=self.paths.positions,
            current_shares=self._shares_from_payload(payload, [asset.symbol for asset in config.universe]),
            cash=float(payload["cash"]) if "cash" in payload else None,
            lot_size=lot_size,
            min_trade_value=min_trade_value,
        )
        output_dir = ensure_dir(config.output_dir / "app")
        write_frame(plan.plan, output_dir / "live_rebalance_plan.csv")
        (output_dir / "live_rebalance_plan.md").write_text(format_live_plan_markdown(plan), encoding="utf-8")

        return {
            "strategy": self._strategy_summary(config_path, config),
            "backtest": self.get_backtest(config_path),
            "as_of_date": plan.as_of_date.date().isoformat(),
            "latest_data_date": latest_data_date,
            "refresh_data": refresh_data,
            "portfolio_value": plan.portfolio_value,
            "cash": plan.cash,
            "trade_count": int((plan.plan["side"] != "HOLD").sum()),
            "orders": self._records(plan.plan[plan.plan["side"] != "HOLD"].copy()),
            "targets": self._records(plan.plan.sort_values("target_weight", ascending=False).copy()),
            "projected_positions": self._projected_positions(plan.plan, plan.cash),
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
        display_path = self._display_path(config_path)
        display_name = CONFIG_DISPLAY_NAMES.get(
            display_path,
            STRATEGY_DISPLAY_NAMES.get(config.strategy.name, config.strategy.name),
        )
        date_range = " - ".join(value for value in [config.data.start, config.data.end] if value)
        return {
            "path": display_path,
            "label": display_name,
            "strategy_name": config.strategy.name,
            "display_name": display_name,
            "data_source": "hybrid" if self._is_hybrid_data_config(config) else config.data.source,
            "can_refresh": self._can_refresh_data(config),
            "universe_size": len(config.universe),
            "date_range": date_range,
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

    @staticmethod
    def _shares_from_payload(payload: dict[str, Any], symbols: list[str]) -> pd.Series | None:
        if "holdings" not in payload:
            return None
        shares = pd.Series(0.0, index=symbols, dtype=float)
        for item in payload.get("holdings") or []:
            symbol = str(item.get("symbol", "")).strip()
            if symbol:
                shares.loc[symbol] = float(item.get("shares") or 0.0)
        return shares

    @staticmethod
    def _projected_positions(plan: pd.DataFrame, cash: float | None) -> dict[str, Any]:
        holdings = [
            {"symbol": str(row.symbol), "shares": float(row.estimated_shares)}
            for row in plan[["symbol", "estimated_shares"]].itertuples(index=False)
        ]
        trade_value = float(plan["trade_value"].sum()) if "trade_value" in plan.columns else 0.0
        projected_cash = float(cash or 0.0) - trade_value
        return {"cash": projected_cash, "holdings": holdings}

    def _refresh_market_data(self, config: AppConfig) -> MarketData:
        if config.data.path is None or not config.data.path.exists():
            return download_market_data(self._refresh_data_config(config.data), config.universe)

        cached = load_market_data(config.data)
        if cached.prices.empty:
            return download_market_data(self._refresh_data_config(config.data), config.universe)

        latest_cached = pd.Timestamp(cached.prices["date"].max())
        start = (latest_cached - pd.DateOffset(days=INCREMENTAL_REFRESH_OVERLAP_DAYS)).date().isoformat()
        fresh = download_market_data(self._refresh_data_config(config.data, start=start), config.universe)
        merged = pd.concat([cached.prices, fresh.prices], ignore_index=True)
        merged = (
            merged.sort_values(["date", "symbol"])
            .drop_duplicates(subset=["date", "symbol"], keep="last")
            .reset_index(drop=True)
        )
        return MarketData.from_frame(merged)

    def _refresh_hybrid_market_data(self, config: AppConfig) -> MarketData:
        if config.data.path is None:
            raise ValueError("刷新 hybrid 行情需要在策略配置里设置 data.path")

        cached = load_market_data(config.data) if config.data.path.exists() else None
        start = config.data.start
        if cached is not None and not cached.prices.empty:
            latest_cached = pd.Timestamp(cached.prices["date"].max())
            start = (latest_cached - pd.DateOffset(days=INCREMENTAL_REFRESH_OVERLAP_DAYS)).date().isoformat()

        yahoo_universe = [asset for asset in config.universe if asset.symbol not in HYBRID_AKSHARE_SYMBOLS]
        akshare_universe = [asset for asset in config.universe if asset.symbol in HYBRID_AKSHARE_SYMBOLS]
        frames = []
        if cached is not None:
            frames.append(cached.prices)
        if yahoo_universe:
            yahoo_data = download_market_data(
                DataConfig(
                    source="yahoo",
                    path=None,
                    start=start,
                    end=None,
                    params={"sleep_seconds": float(config.data.params.get("sleep_seconds", 0.2))},
                ),
                yahoo_universe,
            )
            frames.append(yahoo_data.prices)
        if akshare_universe:
            akshare_data = download_market_data(
                DataConfig(
                    source="akshare",
                    path=None,
                    start=start,
                    end=None,
                    params={
                        "adjust": str(config.data.params.get("adjust", "qfq")),
                        "sleep_seconds": float(config.data.params.get("sleep_seconds", 0.2)),
                    },
                ),
                akshare_universe,
            )
            frames.append(akshare_data.prices)
        if not frames:
            raise RuntimeError("hybrid 行情刷新没有获得任何数据")
        merged = pd.concat(frames, ignore_index=True)
        merged = (
            merged.sort_values(["date", "symbol"])
            .drop_duplicates(subset=["date", "symbol"], keep="last")
            .reset_index(drop=True)
        )
        return MarketData.from_frame(merged).slice(config.data.start, None)

    @staticmethod
    def _refresh_data_config(config: DataConfig, start: str | None = None) -> DataConfig:
        return DataConfig(
            source=config.source,
            path=config.path,
            start=start or config.start,
            end=None,
            params=config.params,
        )

    @classmethod
    def _can_refresh_data(cls, config: AppConfig) -> bool:
        return config.data.source in REMOTE_DATA_SOURCES or cls._is_hybrid_data_config(config)

    @staticmethod
    def _is_hybrid_data_config(config: AppConfig) -> bool:
        return config.data.source == "csv" and config.data.path is not None and config.data.path.name == HYBRID_PRICE_FILE

    @staticmethod
    def _latest_data_date(market_data) -> str | None:
        if market_data.prices.empty:
            return None
        return pd.Timestamp(market_data.prices["date"].max()).date().isoformat()

    @staticmethod
    def _load_metrics(path: Path) -> dict[str, float]:
        if not path.exists():
            return {}
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return {
            key: float(value)
            for key, value in raw.items()
            if isinstance(value, int | float) and key in {"annualized_return", "sharpe", "max_drawdown", "total_return"}
        }

    @staticmethod
    def _load_equity_curve(path: Path, years: int) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        frame = pd.read_csv(path)
        if "date" not in frame.columns or "equity" not in frame.columns:
            return []
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.sort_values("date")
        if frame.empty:
            return []
        cutoff = frame["date"].max() - pd.DateOffset(years=years)
        frame = frame[frame["date"] >= cutoff].copy()
        first = float(frame["equity"].iloc[0]) if not frame.empty else 0.0
        if first > 0:
            frame["indexed"] = frame["equity"] / first
        else:
            frame["indexed"] = 1.0
        return [
            {"date": row.date.date().isoformat(), "equity": float(row.equity), "indexed": float(row.indexed)}
            for row in frame.itertuples(index=False)
        ]
