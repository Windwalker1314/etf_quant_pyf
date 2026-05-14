from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from etf_quant.config.schema import AppConfig
from etf_quant.data.dataset import MarketData
from etf_quant.factors.library import compute_factor_panel
from etf_quant.strategies.registry import build_strategy


@dataclass(frozen=True)
class RebalancePlan:
    as_of_date: pd.Timestamp
    target_weights: pd.Series
    plan: pd.DataFrame
    portfolio_value: float | None = None
    cash: float | None = None


def build_rebalance_plan(
    config: AppConfig,
    market_data: MarketData,
    current_weights: pd.Series | None = None,
) -> RebalancePlan:
    close = market_data.close_wide()
    as_of_date = close.index.max()
    strategy = build_strategy(config.strategy).fit(market_data)
    factors = compute_factor_panel(market_data, config.factors)
    target = strategy.generate_weights(as_of_date, market_data, factors).reindex(close.columns).fillna(0.0)
    current = current_weights.reindex(close.columns).fillna(0.0) if current_weights is not None else pd.Series(0.0, index=close.columns)
    plan = pd.DataFrame(
        {
            "symbol": close.columns,
            "current_weight": current.values,
            "target_weight": target.values,
            "trade_weight": (target - current).values,
        }
    )
    return RebalancePlan(as_of_date=as_of_date, target_weights=target, plan=plan)


def load_positions(path: str | Path | None, symbols: list[str]) -> tuple[pd.Series, float]:
    shares = pd.Series(0.0, index=symbols, dtype=float)
    cash = 0.0
    if path is None:
        return shares, cash
    frame = pd.read_csv(path)
    if "symbol" not in frame.columns or "shares" not in frame.columns:
        raise ValueError("positions CSV requires columns: symbol, shares; optional: cash")
    for _, row in frame.iterrows():
        symbol = str(row["symbol"])
        if symbol.upper() == "CASH":
            cash += float(row.get("cash", row.get("shares", 0.0)) or 0.0)
            continue
        if symbol in shares.index:
            shares.loc[symbol] = float(row["shares"])
        elif abs(float(row["shares"])) > 1e-12:
            shares.loc[symbol] = float(row["shares"])
    if "cash" in frame.columns:
        non_cash = frame["symbol"].astype(str).str.upper() != "CASH"
        cash += float(frame.loc[non_cash, "cash"].fillna(0.0).sum())
    return shares, cash


def build_live_rebalance_plan(
    config: AppConfig,
    market_data: MarketData,
    positions_path: str | Path | None = None,
    current_shares: pd.Series | None = None,
    cash: float | None = None,
    lot_size: int = 100,
    min_trade_value: float = 0.0,
) -> RebalancePlan:
    close = market_data.close_wide()
    as_of_date = close.index.max()
    latest_price = close.loc[as_of_date]
    symbols = close.columns.tolist()
    if current_shares is None:
        shares, file_cash = load_positions(positions_path, symbols)
    else:
        shares = current_shares.reindex(symbols).fillna(0.0)
        file_cash = 0.0
    if cash is None:
        cash_value = file_cash
    else:
        cash_value = float(cash) + file_cash

    shares = shares.reindex(symbols).fillna(0.0)
    current_value = shares * latest_price
    portfolio_value = float(current_value.sum() + cash_value)

    base = build_rebalance_plan(config, market_data)
    target_weight = base.target_weights.reindex(symbols).fillna(0.0)
    target_value = target_weight * portfolio_value
    raw_trade_shares = (target_value - current_value) / latest_price.replace(0.0, np.nan)
    rounded_trade_shares = raw_trade_shares.apply(lambda value: _round_to_lot(value, lot_size))
    trade_value = rounded_trade_shares * latest_price
    rounded_trade_shares = rounded_trade_shares.where(trade_value.abs() >= float(min_trade_value), 0.0)
    trade_value = rounded_trade_shares * latest_price
    target_shares_after_trade = shares + rounded_trade_shares
    estimated_value_after_trade = target_shares_after_trade * latest_price
    estimated_cash_after_trade = cash_value - float(trade_value.sum())
    estimated_total_after_trade = float(estimated_value_after_trade.sum() + estimated_cash_after_trade)
    estimated_weight_after_trade = (
        estimated_value_after_trade / estimated_total_after_trade
        if estimated_total_after_trade > 0
        else pd.Series(0.0, index=symbols)
    )

    plan = pd.DataFrame(
        {
            "symbol": symbols,
            "price": latest_price.values,
            "current_shares": shares.values,
            "current_value": current_value.values,
            "current_weight": (current_value / portfolio_value).values if portfolio_value > 0 else 0.0,
            "target_weight": target_weight.values,
            "target_value": target_value.values,
            "trade_shares": rounded_trade_shares.values,
            "trade_value": trade_value.values,
            "estimated_shares": target_shares_after_trade.values,
            "estimated_weight": estimated_weight_after_trade.values,
        }
    )
    plan["side"] = np.where(plan["trade_shares"] > 0, "BUY", np.where(plan["trade_shares"] < 0, "SELL", "HOLD"))
    plan = plan[
        [
            "symbol",
            "side",
            "price",
            "current_shares",
            "current_value",
            "current_weight",
            "target_weight",
            "target_value",
            "trade_shares",
            "trade_value",
            "estimated_shares",
            "estimated_weight",
        ]
    ]
    return RebalancePlan(
        as_of_date=as_of_date,
        target_weights=target_weight,
        plan=plan,
        portfolio_value=portfolio_value,
        cash=cash_value,
    )


def format_live_plan_markdown(plan: RebalancePlan) -> str:
    trade_rows = plan.plan[plan.plan["side"] != "HOLD"].copy()
    if not trade_rows.empty:
        trade_rows = trade_rows.sort_values(["side", "trade_value"], ascending=[True, True])
    lines = [
        f"# ETF Daily Trading Plan - {plan.as_of_date.date().isoformat()}",
        "",
        f"- Portfolio value: {plan.portfolio_value:,.2f}" if plan.portfolio_value is not None else "- Portfolio value: n/a",
        f"- Cash: {plan.cash:,.2f}" if plan.cash is not None else "- Cash: n/a",
        f"- Trade count: {len(trade_rows)}",
        "",
        "## Orders",
        "",
    ]
    if trade_rows.empty:
        lines.append("No trades. Keep current holdings.")
    else:
        lines.append("| Symbol | Side | Shares | Est. Price | Est. Amount | Target Weight |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
        for _, row in trade_rows.iterrows():
            lines.append(
                "| {symbol} | {side} | {shares:,.0f} | {price:,.3f} | {amount:,.2f} | {weight:.2%} |".format(
                    symbol=row["symbol"],
                    side=row["side"],
                    shares=row["trade_shares"],
                    price=row["price"],
                    amount=row["trade_value"],
                    weight=row["target_weight"],
                )
            )
    lines.extend(
        [
            "",
            "## Full Target",
            "",
            "| Symbol | Current Weight | Target Weight | Est. Weight | Current Shares | Est. Shares |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in plan.plan.sort_values("target_weight", ascending=False).iterrows():
        lines.append(
            "| {symbol} | {current_weight:.2%} | {target_weight:.2%} | {estimated_weight:.2%} | {current_shares:,.0f} | {estimated_shares:,.0f} |".format(
                symbol=row["symbol"],
                current_weight=row["current_weight"],
                target_weight=row["target_weight"],
                estimated_weight=row["estimated_weight"],
                current_shares=row["current_shares"],
                estimated_shares=row["estimated_shares"],
            )
        )
    return "\n".join(lines) + "\n"


def _round_to_lot(value: float, lot_size: int) -> float:
    if not np.isfinite(value):
        return 0.0
    lot = max(1, int(lot_size))
    return float(np.trunc(value / lot) * lot)
