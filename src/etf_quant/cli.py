from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from etf_quant.backtest.engine import BacktestEngine
from etf_quant.config.loader import load_config, load_universe
from etf_quant.data.macro import download_fred_series, macro_from_price_ratio, save_macro_series
from etf_quant.data.sample import write_sample_prices
from etf_quant.data.sources import download_market_data, load_market_data
from etf_quant.io import ensure_dir, write_frame, write_metrics
from etf_quant.research.sweep import (
    run_bigquant_turnover_sweep,
    run_macro_filter_sweep,
    run_macro_risk_sweep,
    run_macro_trend_sweep,
)
from etf_quant.live.rebalance import build_live_rebalance_plan, build_rebalance_plan, format_live_plan_markdown
from etf_quant.strategies.registry import build_strategy
from etf_quant.validation.walk_forward import WalkForwardValidator


def cmd_init_sample_data(args: argparse.Namespace) -> None:
    assets = load_universe(args.config)
    output = write_sample_prices(args.output, assets, start=args.start, end=args.end)
    print(f"sample data written: {output}")


def cmd_download_data(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    output = args.output or config.data.path
    if output is None:
        raise ValueError("download-data requires --output or data.path in config")
    market_data = download_market_data(config.data, config.universe)
    write_frame(market_data.prices, output)
    print(f"market data written: {output}")


def cmd_download_macro(args: argparse.Namespace) -> None:
    data = download_fred_series(args.series)
    save_macro_series(data, args.output)
    print(f"macro data written: {args.output}")
    print(data.tail().to_string(index=False))


def cmd_macro_price_ratio(args: argparse.Namespace) -> None:
    frame = pd.read_csv(args.prices)
    data = macro_from_price_ratio(frame, args.numerator, args.denominator, args.output_col)
    save_macro_series(data, args.output)
    print(f"macro ratio written: {args.output}")
    print(data.tail().to_string(index=False))


def cmd_validate_data(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    market_data = load_market_data(config.data)
    close = market_data.close_wide()
    returns = close.pct_change()
    threshold = float(args.jump_threshold)
    issues = []
    for symbol in returns.columns:
        jumps = returns[symbol][returns[symbol].abs() > threshold].dropna()
        for date, value in jumps.items():
            issues.append({"date": date.date().isoformat(), "symbol": symbol, "return": float(value)})
    if not issues:
        print(f"data validation passed: no abs daily return > {threshold:.1%}")
        return
    print(f"data validation found {len(issues)} large jumps > {threshold:.1%}:")
    for issue in issues[:50]:
        print(issue)
    if len(issues) > 50:
        print(f"... {len(issues) - 50} more")


def cmd_backtest(args: argparse.Namespace) -> None:
    from etf_quant.backtest.plotting import plot_equity_curve

    config = load_config(args.config)
    output_dir = ensure_dir(config.output_dir)
    market_data = load_market_data(config.data)
    strategy = build_strategy(config.strategy).fit(market_data)
    result = BacktestEngine(config.backtest).run(market_data, config.factors, strategy)
    write_frame(result.equity_curve, output_dir / "equity_curve.csv")
    write_frame(result.weights, output_dir / "weights.csv")
    write_metrics(result.metrics, output_dir / "metrics.yaml")
    plot_equity_curve(result.equity_curve, output_dir / "equity_curve.png", result.metrics)
    print(f"backtest complete: {output_dir}")
    print(result.metrics)


def cmd_walk_forward(args: argparse.Namespace) -> None:
    from etf_quant.backtest.plotting import plot_equity_curve

    config = load_config(args.config)
    output_dir = ensure_dir(config.output_dir)
    market_data = load_market_data(config.data)
    result = WalkForwardValidator(config).run(market_data)
    write_frame(result.equity_curve, output_dir / "walk_forward_equity.csv")
    write_frame(result.fold_metrics, output_dir / "walk_forward_folds.csv")
    write_metrics(result.metrics, output_dir / "walk_forward_metrics.yaml")
    plot_equity_curve(
        result.equity_curve,
        output_dir / "walk_forward_equity.png",
        result.metrics,
        title="Walk-forward Equity Curve",
    )
    print(f"walk-forward complete: {output_dir}")
    print(result.metrics)


def cmd_rebalance(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    output_dir = ensure_dir(config.output_dir)
    market_data = load_market_data(config.data)
    plan = build_rebalance_plan(config, market_data)
    write_frame(plan.plan, output_dir / "rebalance_plan.csv")
    print(f"rebalance plan complete for {plan.as_of_date.date()}: {output_dir / 'rebalance_plan.csv'}")


def cmd_live_plan(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    output_dir = ensure_dir(args.output_dir or config.output_dir / "live")
    if args.refresh_data:
        market_data = download_market_data(config.data, config.universe)
        if config.data.path is None:
            raise ValueError("live-plan --refresh-data requires data.path in config")
        write_frame(market_data.prices, config.data.path)
        print(f"market data refreshed: {config.data.path}")
    else:
        market_data = load_market_data(config.data)

    plan = build_live_rebalance_plan(
        config,
        market_data,
        positions_path=args.positions,
        cash=args.cash,
        lot_size=args.lot_size,
        min_trade_value=args.min_trade_value,
    )
    csv_path = output_dir / "live_rebalance_plan.csv"
    md_path = output_dir / "live_rebalance_plan.md"
    write_frame(plan.plan, csv_path)
    md_path.write_text(format_live_plan_markdown(plan), encoding="utf-8")
    print(f"live plan complete for data date {plan.as_of_date.date()}: {output_dir}")
    print(format_live_plan_markdown(plan))


def cmd_app(args: argparse.Namespace) -> None:
    from etf_quant.app.server import run_server

    run_server(args.host, args.port, Path(args.root).resolve(), open_browser=args.open)


def cmd_sweep_bigquant(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    market_data = load_market_data(config.data)
    output_dir = args.output_dir or (
        Path("outputs") / "experiments" / config.strategy.name / Path(args.config).stem / "sweeps"
    )
    frame = run_bigquant_turnover_sweep(config, market_data, output_dir=output_dir, preset=args.preset)
    print(f"bigquant sweep complete: {output_dir}")
    print(frame.head(10).to_string(index=False))


def cmd_sweep_macro_risk(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    market_data = load_market_data(config.data)
    output_dir = args.output_dir or (
        Path("outputs") / "experiments" / "macro_risk_rotation" / Path(args.config).stem / "sweeps"
    )
    frame = run_macro_risk_sweep(config, market_data, output_dir=output_dir)
    print(f"macro risk sweep complete: {output_dir}")
    print(frame.head(10).to_string(index=False))


def cmd_sweep_macro_filter(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    market_data = load_market_data(config.data)
    output_dir = args.output_dir or (
        Path("outputs") / "experiments" / "macro_risk_rotation" / Path(args.config).stem / "sweeps"
    )
    frame = run_macro_filter_sweep(config, market_data, output_dir=output_dir)
    print(f"macro filter sweep complete: {output_dir}")
    print(frame.head(10).to_string(index=False))


def cmd_sweep_macro_trend(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    market_data = load_market_data(config.data)
    output_dir = args.output_dir or (
        Path("outputs") / "experiments" / "macro_risk_rotation" / Path(args.config).stem / "sweeps"
    )
    frame = run_macro_trend_sweep(config, market_data, output_dir=output_dir)
    print(f"macro trend sweep complete: {output_dir}")
    print(frame.head(10).to_string(index=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ETF Quant daily research framework")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-sample-data", help="generate local sample OHLCV data")
    init.add_argument("--config", default="configs/universe.yaml")
    init.add_argument("--output", default="data/raw/sample_prices.csv")
    init.add_argument("--start", default="2018-01-01")
    init.add_argument("--end", default="2024-12-31")
    init.set_defaults(func=cmd_init_sample_data)

    download = sub.add_parser("download-data", help="download remote market data to CSV")
    download.add_argument("--config", required=True)
    download.add_argument("--output", default=None)
    download.set_defaults(func=cmd_download_data)

    macro_download = sub.add_parser("download-macro", help="download FRED macro series to CSV")
    macro_download.add_argument("--series", nargs="+", required=True)
    macro_download.add_argument("--output", required=True)
    macro_download.set_defaults(func=cmd_download_macro)

    macro_ratio = sub.add_parser("macro-price-ratio", help="build a macro proxy series from two price symbols")
    macro_ratio.add_argument("--prices", required=True)
    macro_ratio.add_argument("--numerator", required=True)
    macro_ratio.add_argument("--denominator", required=True)
    macro_ratio.add_argument("--output-col", required=True)
    macro_ratio.add_argument("--output", required=True)
    macro_ratio.set_defaults(func=cmd_macro_price_ratio)

    validate = sub.add_parser("validate-data", help="run basic market data quality checks")
    validate.add_argument("--config", required=True)
    validate.add_argument("--jump-threshold", default=0.20)
    validate.set_defaults(func=cmd_validate_data)

    backtest = sub.add_parser("backtest", help="run a single backtest")
    backtest.add_argument("--config", required=True)
    backtest.set_defaults(func=cmd_backtest)

    walk = sub.add_parser("walk-forward", help="run walk-forward validation")
    walk.add_argument("--config", required=True)
    walk.set_defaults(func=cmd_walk_forward)

    rebalance = sub.add_parser("rebalance", help="create daily rebalance plan")
    rebalance.add_argument("--config", required=True)
    rebalance.set_defaults(func=cmd_rebalance)

    live = sub.add_parser("live-plan", help="create a pre-open trading plan with shares and orders")
    live.add_argument("--config", required=True)
    live.add_argument("--positions", default=None, help="CSV with columns symbol,shares and optional cash")
    live.add_argument("--cash", type=float, default=None, help="cash balance to add to portfolio value")
    live.add_argument("--output-dir", default=None)
    live.add_argument("--refresh-data", action="store_true", help="download latest data before building the plan")
    live.add_argument("--lot-size", type=int, default=100)
    live.add_argument("--min-trade-value", type=float, default=0.0)
    live.set_defaults(func=cmd_live_plan)

    app = sub.add_parser("app", help="run the personal local web app")
    app.add_argument("--host", default="127.0.0.1")
    app.add_argument("--port", type=int, default=8765)
    app.add_argument("--root", default=".")
    app.add_argument("--open", action="store_true", help="open the app in the default browser")
    app.set_defaults(func=cmd_app)

    sweep = sub.add_parser("sweep-bigquant", help="batch test bigquant turnover-control parameters")
    sweep.add_argument("--config", required=True)
    sweep.add_argument("--output-dir", default=None)
    sweep.add_argument("--preset", choices=["turnover", "gap"], default="turnover")
    sweep.set_defaults(func=cmd_sweep_bigquant)

    macro = sub.add_parser("sweep-macro-risk", help="batch test macro proxy risk-on/risk-off parameters")
    macro.add_argument("--config", required=True)
    macro.add_argument("--output-dir", default=None)
    macro.set_defaults(func=cmd_sweep_macro_risk)

    macro_filter = sub.add_parser("sweep-macro-filter", help="batch test FRED macro stress filter parameters")
    macro_filter.add_argument("--config", required=True)
    macro_filter.add_argument("--output-dir", default=None)
    macro_filter.set_defaults(func=cmd_sweep_macro_filter)

    macro_trend = sub.add_parser("sweep-macro-trend", help="batch test macro price-trend proxy filters")
    macro_trend.add_argument("--config", required=True)
    macro_trend.add_argument("--output-dir", default=None)
    macro_trend.set_defaults(func=cmd_sweep_macro_trend)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
