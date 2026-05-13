from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def annualized_return(equity: pd.Series, periods_per_year: int = 252) -> float:
    if len(equity) < 2:
        return 0.0
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    years = len(equity) / periods_per_year
    return float((1.0 + total_return) ** (1.0 / years) - 1.0)


def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    return float(returns.std(ddof=0) * np.sqrt(periods_per_year))


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
    excess = returns - risk_free_rate / periods_per_year
    vol = excess.std(ddof=0)
    if vol == 0 or np.isnan(vol):
        return 0.0
    return float(excess.mean() / vol * np.sqrt(periods_per_year))


def summarize_performance(equity: pd.Series) -> dict[str, float]:
    returns = equity.pct_change().fillna(0.0)
    return {
        "annualized_return": annualized_return(equity),
        "annualized_volatility": annualized_volatility(returns),
        "sharpe": sharpe_ratio(returns),
        "max_drawdown": max_drawdown(equity),
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1.0) if len(equity) else 0.0,
    }


def summarize_portfolio_behavior(
    weights: pd.DataFrame,
    turnover: pd.Series,
    periods_per_year: int = 252,
) -> dict[str, float]:
    gross_exposure = weights.clip(lower=0.0).sum(axis=1)
    active_positions = weights.gt(1e-9).sum(axis=1)
    max_weight = weights.max(axis=1)
    trade_days = turnover.gt(1e-9).sum()
    return {
        "annualized_turnover": float(turnover.mean() * periods_per_year),
        "avg_daily_turnover": float(turnover.mean()),
        "trade_days": float(trade_days),
        "avg_gross_exposure": float(gross_exposure.mean()),
        "cash_days": float(gross_exposure.lt(0.99).sum()),
        "avg_active_positions": float(active_positions.mean()),
        "avg_max_weight": float(max_weight.mean()),
        "p95_max_weight": float(max_weight.quantile(0.95)),
    }
