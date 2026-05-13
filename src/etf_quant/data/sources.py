from __future__ import annotations

import json
import os
import time
from datetime import timezone
from pathlib import Path
from typing import Iterable, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from etf_quant.config.schema import Asset, DataConfig
from etf_quant.data.dataset import MarketData


class DataSource(Protocol):
    def load(self, config: DataConfig) -> MarketData:
        ...


class CsvDataSource:
    def load(self, config: DataConfig) -> MarketData:
        if config.path is None:
            raise ValueError("CSV data source requires data.path")
        frame = pd.read_csv(config.path)
        data = MarketData.from_frame(frame)
        return data.slice(config.start, config.end)


class YahooFinanceDataSource:
    base_url = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    def load(self, config: DataConfig) -> MarketData:
        if config.path is not None and Path(config.path).exists():
            return CsvDataSource().load(config)
        universe = [
            Asset(**item) if isinstance(item, dict) else item
            for item in config.params.get("universe", [])
        ]
        if not universe:
            raise ValueError("Yahoo data source requires data.params.universe")
        return self.download(
            universe=universe,
            start=config.start,
            end=config.end,
            symbol_map=config.params.get("symbol_map", {}),
            sleep_seconds=float(config.params.get("sleep_seconds", 0.2)),
        )

    def download(
        self,
        universe: Iterable[Asset],
        start: str | None,
        end: str | None,
        symbol_map: dict[str, str] | None = None,
        sleep_seconds: float = 0.2,
    ) -> MarketData:
        symbol_map = symbol_map or {}
        frames = []
        failures = []
        for asset in universe:
            yahoo_symbol = symbol_map.get(asset.symbol, self._to_yahoo_symbol(asset.symbol))
            try:
                frames.append(self._download_one(asset.symbol, yahoo_symbol, start, end))
            except Exception as exc:  # noqa: BLE001 - collect all provider failures.
                failures.append(f"{asset.symbol}({yahoo_symbol}): {exc}")
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        if not frames:
            raise RuntimeError("Yahoo download failed for all symbols: " + "; ".join(failures))
        if failures:
            print("Yahoo download warnings: " + "; ".join(failures))
        return MarketData.from_frame(pd.concat(frames, ignore_index=True))

    def _download_one(
        self,
        original_symbol: str,
        yahoo_symbol: str,
        start: str | None,
        end: str | None,
    ) -> pd.DataFrame:
        period1 = self._to_epoch(start or "1970-01-01")
        period2 = self._to_epoch(end) if end else int(time.time())
        query = urlencode(
            {
                "period1": period1,
                "period2": period2,
                "interval": "1d",
                "events": "history",
                "includeAdjustedClose": "true",
            }
        )
        url = f"{self.base_url.format(symbol=yahoo_symbol)}?{query}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload.get("chart", {}).get("result")
        error = payload.get("chart", {}).get("error")
        if not result:
            raise RuntimeError(error or "empty response")
        result0 = result[0]
        timestamps = result0.get("timestamp") or []
        quote = (result0.get("indicators", {}).get("quote") or [{}])[0]
        adjusted = (result0.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(timestamps, unit="s").date,
                "symbol": original_symbol,
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "close": adjusted or quote.get("close"),
                "volume": quote.get("volume"),
            }
        )
        frame = frame.dropna(subset=["open", "high", "low", "close"])
        if frame.empty:
            raise RuntimeError("no valid OHLC rows")
        return frame

    @staticmethod
    def _to_epoch(date_value: str) -> int:
        return int(pd.Timestamp(date_value, tz=timezone.utc).timestamp())

    @staticmethod
    def _to_yahoo_symbol(symbol: str) -> str:
        if symbol.endswith(".SH"):
            return symbol.replace(".SH", ".SS")
        if symbol.endswith(".SZ"):
            return symbol
        return symbol


class AkShareDataSource:
    def load(self, config: DataConfig) -> MarketData:
        if config.path is not None and Path(config.path).exists():
            return CsvDataSource().load(config)
        universe = [
            Asset(**item) if isinstance(item, dict) else item
            for item in config.params.get("universe", [])
        ]
        if not universe:
            raise ValueError("AkShare data source requires data.params.universe")
        return self.download(
            universe=universe,
            start=config.start,
            end=config.end,
            adjust=str(config.params.get("adjust", "qfq")),
            sleep_seconds=float(config.params.get("sleep_seconds", 0.2)),
        )

    def download(
        self,
        universe: Iterable[Asset],
        start: str | None,
        end: str | None,
        adjust: str = "qfq",
        sleep_seconds: float = 0.2,
    ) -> MarketData:
        try:
            import akshare as ak
        except ImportError as exc:
            raise ImportError("AkShare data source requires installing akshare") from exc

        start_date = self._format_date(start or "1990-01-01")
        end_date = self._format_date(end or pd.Timestamp.today().strftime("%Y-%m-%d"))
        frames = []
        failures = []
        for asset in universe:
            code = self._strip_exchange(asset.symbol)
            try:
                raw = self._download_one(ak, asset.symbol, code, start_date, end_date, adjust)
                frames.append(self._normalize(raw, asset.symbol))
            except Exception as exc:  # noqa: BLE001 - collect all provider failures.
                failures.append(f"{asset.symbol}({code}): {exc}")
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        if not frames:
            raise RuntimeError("AkShare download failed for all symbols: " + "; ".join(failures))
        if failures:
            print("AkShare download warnings: " + "; ".join(failures))
        return MarketData.from_frame(pd.concat(frames, ignore_index=True)).slice(start, end)

    def _download_one(
        self,
        ak,
        original_symbol: str,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        errors = []
        for fn_name in ("fund_etf_hist_em", "fund_lof_hist_em"):
            try:
                frame = getattr(ak, fn_name)(
                    symbol=code,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                )
                if frame is not None and not frame.empty:
                    return frame
            except Exception as exc:  # noqa: BLE001 - fallback from ETF to LOF.
                errors.append(f"{fn_name}: {exc}")
        try:
            frame = ak.fund_etf_hist_sina(symbol=self._to_sina_symbol(original_symbol))
            if frame is not None and not frame.empty:
                return frame
        except Exception as exc:  # noqa: BLE001 - collect final fallback failure.
            errors.append(f"fund_etf_hist_sina: {exc}")
        raise RuntimeError("; ".join(errors) or "empty response")

    @staticmethod
    def _normalize(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        columns = {
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
            "换手率": "turn",
            "date": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "amount": "amount",
        }
        frame = raw.rename(columns=columns)
        frame = frame.loc[:, ~frame.columns.duplicated()]
        wanted = list(dict.fromkeys(columns.values()))
        frame = frame[[col for col in wanted if col in frame.columns]].copy()
        frame["symbol"] = symbol
        frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
        if "volume" not in frame.columns:
            frame["volume"] = 0.0
        return frame

    @staticmethod
    def _strip_exchange(symbol: str) -> str:
        return symbol.split(".")[0]

    @staticmethod
    def _to_sina_symbol(symbol: str) -> str:
        code = symbol.split(".")[0]
        if symbol.endswith(".SH"):
            return f"sh{code}"
        if symbol.endswith(".SZ"):
            return f"sz{code}"
        return code

    @staticmethod
    def _format_date(date_value: str) -> str:
        return pd.Timestamp(date_value).strftime("%Y%m%d")


class TushareDataSource:
    def load(self, config: DataConfig) -> MarketData:
        if config.path is not None and Path(config.path).exists():
            return CsvDataSource().load(config)
        universe = [
            Asset(**item) if isinstance(item, dict) else item
            for item in config.params.get("universe", [])
        ]
        if not universe:
            raise ValueError("Tushare data source requires data.params.universe")
        return self.download(
            universe=universe,
            start=config.start,
            end=config.end,
            token=config.params.get("token") or os.environ.get("TUSHARE_TOKEN"),
            sleep_seconds=float(config.params.get("sleep_seconds", 0.2)),
        )

    def download(
        self,
        universe: Iterable[Asset],
        start: str | None,
        end: str | None,
        token: str | None,
        sleep_seconds: float = 0.2,
    ) -> MarketData:
        if not token:
            raise ValueError("Tushare data source requires data.params.token or TUSHARE_TOKEN")
        try:
            import tushare as ts
        except ImportError as exc:
            raise ImportError("Tushare data source requires installing tushare") from exc

        pro = ts.pro_api(token)
        start_date = AkShareDataSource._format_date(start or "1990-01-01")
        end_date = AkShareDataSource._format_date(end or pd.Timestamp.today().strftime("%Y-%m-%d"))
        frames = []
        failures = []
        for asset in universe:
            try:
                raw = pro.fund_daily(ts_code=asset.symbol, start_date=start_date, end_date=end_date)
                if raw is None or raw.empty:
                    raise RuntimeError("empty response")
                frames.append(self._normalize(raw, asset.symbol))
            except Exception as exc:  # noqa: BLE001 - collect all provider failures.
                failures.append(f"{asset.symbol}: {exc}")
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        if not frames:
            raise RuntimeError("Tushare download failed for all symbols: " + "; ".join(failures))
        if failures:
            print("Tushare download warnings: " + "; ".join(failures))
        return MarketData.from_frame(pd.concat(frames, ignore_index=True))

    @staticmethod
    def _normalize(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        frame = raw.rename(
            columns={
                "trade_date": "date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "vol": "volume",
                "amount": "amount",
            }
        )
        columns = [col for col in ["date", "open", "high", "low", "close", "volume", "amount"] if col in frame.columns]
        frame = frame[columns].copy()
        frame["date"] = pd.to_datetime(frame["date"], format="%Y%m%d")
        frame["symbol"] = symbol
        if "volume" not in frame.columns:
            frame["volume"] = 0.0
        return frame


DATA_SOURCE_REGISTRY: dict[str, DataSource] = {
    "akshare": AkShareDataSource(),
    "csv": CsvDataSource(),
    "tushare": TushareDataSource(),
    "yahoo": YahooFinanceDataSource(),
}


def load_market_data(config: DataConfig) -> MarketData:
    try:
        source = DATA_SOURCE_REGISTRY[config.source]
    except KeyError as exc:
        available = ", ".join(sorted(DATA_SOURCE_REGISTRY))
        raise ValueError(f"Unknown data source {config.source!r}. Available: {available}") from exc
    return source.load(config)


def download_market_data(config: DataConfig, universe: list[Asset]) -> MarketData:
    if config.source == "csv":
        raise ValueError("download-data requires a remote data source, e.g. source: yahoo")
    data_config = DataConfig(
        source=config.source,
        path=None,
        start=config.start,
        end=config.end,
        params={**config.params, "universe": universe},
    )
    return load_market_data(data_config)
