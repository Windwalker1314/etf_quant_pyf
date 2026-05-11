from __future__ import annotations

import argparse

from etf_quant.backtest.engine import BacktestEngine
from etf_quant.config.loader import load_config, load_universe
from etf_quant.data.sample import write_sample_prices
from etf_quant.data.sources import load_market_data
from etf_quant.io import ensure_dir, write_frame, write_metrics
from etf_quant.live.rebalance import build_rebalance_plan
from etf_quant.strategies.registry import build_strategy
from etf_quant.validation.walk_forward import WalkForwardValidator


def cmd_init_sample_data(args: argparse.Namespace) -> None:
    assets = load_universe(args.config)
    output = write_sample_prices(args.output, assets)
    print(f"sample data written: {output}")


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
    plot_equity_curve(result.equity_curve, output_dir / "equity_curve.png")
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
    plot_equity_curve(result.equity_curve, output_dir / "walk_forward_equity.png")
    print(f"walk-forward complete: {output_dir}")
    print(result.metrics)


def cmd_rebalance(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    output_dir = ensure_dir(config.output_dir)
    market_data = load_market_data(config.data)
    plan = build_rebalance_plan(config, market_data)
    write_frame(plan.plan, output_dir / "rebalance_plan.csv")
    print(f"rebalance plan complete for {plan.as_of_date.date()}: {output_dir / 'rebalance_plan.csv'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ETF Quant daily research framework")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-sample-data", help="generate local sample OHLCV data")
    init.add_argument("--config", default="configs/universe.yaml")
    init.add_argument("--output", default="data/raw/sample_prices.csv")
    init.set_defaults(func=cmd_init_sample_data)

    backtest = sub.add_parser("backtest", help="run a single backtest")
    backtest.add_argument("--config", required=True)
    backtest.set_defaults(func=cmd_backtest)

    walk = sub.add_parser("walk-forward", help="run walk-forward validation")
    walk.add_argument("--config", required=True)
    walk.set_defaults(func=cmd_walk_forward)

    rebalance = sub.add_parser("rebalance", help="create daily rebalance plan")
    rebalance.add_argument("--config", required=True)
    rebalance.set_defaults(func=cmd_rebalance)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
