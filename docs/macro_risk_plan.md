# Macro Risk Overlay Research Plan

Date: 2026-05-12

## Motivation

The current short-sample ETF rotation line works well on recent A/H ETF data, but the global long-history transfer test exposes a different problem:

| Strategy | Annualized return | Sharpe | Max drawdown |
| --- | ---: | ---: | ---: |
| Global equal weight | 6.22% | 0.49 | -42.04% |
| Global BigQuant transfer | 8.05% | 0.65 | -22.27% |
| Macro proxy risk rotation candidate | 9.47% | 0.72 | -25.07% |
| Credit proxy balanced candidate | 9.22% | 0.73 | -22.79% |

The useful direction is not just another short-horizon ranker. Long samples include 2008, 2011, 2015, 2020 and 2022-style regime shifts, so the model needs an explicit risk-on/risk-off overlay and a broader defensive allocation set.

## First Experiment: Price-Based Macro Proxy

Implementation:

- Added `macro_risk_rotation`.
- Added `configs/global_etf_macro_risk_yahoo.yaml`.
- Added CLI sweep:

```bash
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli sweep-macro-risk --config configs/global_etf_macro_risk_yahoo.yaml
```

Outputs:

- `outputs/global/strategies/macro_risk_rotation_yahoo/`
- `outputs/experiments/macro_risk_rotation/global_etf_macro_risk_yahoo/sweeps/macro_risk_sweep.csv`
- `outputs/experiments/macro_risk_rotation/global_etf_macro_risk_yahoo/sweeps/macro_risk_sweep_top20.csv`

Logic:

- Risk assets: `SPY`, `QQQ`, `IWM`, `EFA`, `EEM`, `FXI`, `VNQ`.
- Defensive assets: `IEF`, `TLT`, `GLD`.
- Risk-on requires:
  - Risk-asset breadth above long moving averages.
  - Average risk momentum above threshold.
  - Recent broad risk momentum not in a crash regime.
- Risk-on allocation: top 3 risk assets by multi-window momentum.
- Risk-off allocation: top 2 defensive assets by momentum, with optional cash.
- Weighting: inverse volatility.

Current candidate:

```yaml
breadth_threshold: 0.55
risk_score_threshold: 0.03
crash_momentum_threshold: -0.04
cash_weight_when_defensive: 0.25
defensive_hold_num: 2
```

Result on `2006-02-06` to `2026-05-11`:

| Annualized return | Annualized vol | Sharpe | Max drawdown | Annualized turnover | Avg gross exposure |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 9.47% | 13.84% | 0.72 | -25.07% | 6.99 | 90.49% |

Top sweep result by Sharpe:

| Annualized return | Annualized vol | Sharpe | Max drawdown | Cash in defensive | Defensive assets |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10.20% | 14.57% | 0.74 | -25.19% | 0% | 2 |

Readout:

- The overlay improves long-sample return and Sharpe versus the BigQuant transfer baseline.
- It does not yet solve the drawdown problem: the best tested drawdown is still about `-25%`.
- Cash reduces volatility and exposure, but in this proxy-only version it does not bring max drawdown below the current BigQuant transfer baseline.
- The improvement likely comes from cross-asset regime allocation, not from true macro information yet.

## Macro Factors Worth Adding

These should be tested as lagged monthly state variables, not same-day signals.

| Factor | Candidate source/series | Why it matters | Expected use |
| --- | --- | --- | --- |
| Yield curve | FRED `T10Y2Y` | Inversion and re-steepening often flag late-cycle/recession risk. | Reduce equity beta when curve is deeply inverted or rapidly steepening after inversion. |
| Credit spread | FRED `BAMLH0A0HYM2` | Captures stress in risky financing conditions. | Risk-off when high-yield OAS widens fast or exceeds percentile threshold. |
| Financial conditions | FRED `NFCI` | Aggregates money-market, debt, equity and banking stress. | Risk-off when conditions tighten materially. |
| Policy rate trend | FRED `FEDFUNDS` or effective fed funds equivalent | Hiking/rapid easing regimes carry different asset leadership. | Distinguish early easing, panic easing and hiking pressure. |
| Inflation / real-rate pressure | FRED CPI plus Treasury yields | Helps separate equity-friendly easing from inflationary rate shock. | Prefer gold/commodities/TIPS-like assets when real-rate/inflation pressure is high. |
| USD liquidity / dollar trend | DXY ETF/proxy, broad dollar series | Strong dollar often hurts EM/China and commodities. | Penalize `EEM`/`FXI`/commodity sleeve in dollar stress. |
| China credit / social financing proxy | local macro source if available | More relevant for A-share bull/bear cycles than US-only macro. | Control A-share ETF exposure; possible A/H-specific overlay. |

## Second Experiment: Credit Risk Proxy

FRED direct CSV downloads were unstable in the current network session, so the first credit experiment uses a tradable proxy:

- Downloaded `HYG` and `LQD` from Yahoo to `data/raw/macro/credit_proxy_yahoo_prices.csv`.
- Built `credit_risk_ratio = HYG / LQD` in `data/raw/macro/credit_risk_ratio.csv`.
- Applied a 21-calendar-day lag before the ratio can affect ETF weights.
- Risk-off if the lagged credit ratio is too far below its moving average.

Commands:

```bash
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli download-data --config configs/macro_credit_proxy_yahoo.yaml
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli macro-price-ratio --prices data/raw/macro/credit_proxy_yahoo_prices.csv --numerator HYG --denominator LQD --output-col credit_risk_ratio --output data/raw/macro/credit_risk_ratio.csv
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli sweep-macro-trend --config configs/global_etf_macro_risk_yahoo.yaml
```

Outputs:

- `outputs/experiments/macro_risk_rotation/global_etf_macro_risk_yahoo/sweeps/macro_trend_sweep.csv`
- `outputs/experiments/macro_risk_rotation/global_etf_macro_risk_yahoo/sweeps/macro_trend_sweep_top20.csv`

Candidate comparison:

| Candidate | Annualized return | Annualized vol | Sharpe | Max drawdown | Annualized turnover | Avg gross exposure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No credit proxy | 9.47% | 13.84% | 0.72 | -25.07% | 6.99 | 90.49% |
| Credit proxy balanced | 9.22% | 13.37% | 0.73 | -22.79% | 7.39 | 88.77% |
| Credit proxy low-drawdown | 8.20% | 12.47% | 0.69 | -20.22% | 7.04 | 86.17% |

Current config uses the balanced candidate:

```yaml
macro_data_path: ../data/raw/macro/credit_risk_ratio.csv
macro_lag_days: 21
macro_trend_col: credit_risk_ratio
macro_trend_ma_window: 126
macro_trend_min_gap: -0.01
macro_trend_min_momentum_63d: null
```

Readout:

- Credit stress information helps: the balanced candidate keeps most of the return improvement while pulling max drawdown close to the BigQuant transfer baseline.
- The low-drawdown candidate gets max drawdown near `-20%`, but gives up too much return for the current objective.
- This supports the idea that macro/credit filters should be treated as a drawdown governor, not as the primary return engine.
- The proxy should eventually be replaced or cross-checked with FRED `BAMLH0A0HYM2` once the downloader is reliable.

## Next Experiments

1. Make the macro downloader more robust for FRED and cache true `BAMLH0A0HYM2`, `T10Y2Y`, `NFCI`, and `FEDFUNDS`.
2. Add a faster sweep path that reuses precomputed trend/macro panels.
3. Test two validation modes:
   - long global ETF history, 2006-2026,
   - A/H hybrid sample, 2020-2026, only as a short-sample sanity check.
4. Optimize for constrained objectives, not max Sharpe alone:
   - primary: max drawdown below `-20%`;
   - secondary: annualized return above `10%`;
   - tertiary: annualized turnover below `8`.
5. Add China-specific macro or proxy indicators for A-share exposure, because US credit stress alone cannot explain 2008/2015 A-share regime changes.

## Current Recommendation

Do not replace the current A/H BigQuant line yet. Use `macro_risk_rotation` as a long-history research baseline. The credit proxy experiment is promising because it lifts long-sample return versus the BigQuant transfer baseline while keeping drawdown in the same neighborhood and cutting turnover sharply. The next question is whether true macro stress data can push max drawdown below `-20%` without giving back the return improvement.
