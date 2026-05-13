# ETF Quant iOS App Demo Product Design

## Product Positioning

ETF Quant iOS is a daily decision companion for ETF rotation strategies. The app does not try to replace a broker in the first version. It helps the user choose a strategy, review the latest allocation, receive a daily rebalance reminder, and inspect the strategy's backtest curve before placing trades manually.

## Target User

- Individual quant investor running the ETF Quant research framework locally.
- Needs a quick morning check on whether the portfolio should rebalance.
- Wants strategy confidence signals without opening notebooks or CSV files.

## MVP Scope

1. Strategy selection
   - Show available strategies with core metrics.
   - Highlight the currently selected strategy.
   - Preview the target allocation and rebalance urgency.

2. Daily rebalance reminder
   - Let the user set a daily reminder time.
   - Request iOS notification permission.
   - Schedule a repeating local notification.

3. Backtest curve
   - Show a compact equity curve.
   - Show annualized return, max drawdown, Sharpe ratio, and latest signal.
   - Compare strategy value against an equal-weight baseline in the UI model.

4. Rebalance plan preview
   - Show buy/sell/hold actions for the latest plan.
   - Keep this as decision support only in the demo.

## Information Architecture

- Today: selected strategy, next reminder, portfolio value, rebalance actions.
- Strategies: strategy picker with metrics, allocation preview, risk notes.
- Backtest: curve, key metrics, recent regime notes.
- Settings: reminder time, notification permission, data connection placeholder.

## First Demo Decisions

- Native iOS demo uses SwiftUI, Swift Charts, and UserNotifications.
- Data is embedded as deterministic demo data, so the app can run without a backend.
- A local browser demo mirrors the mobile UI for machines that do not currently have full Xcode installed.
- Future integration point: replace `DemoStrategyRepository` with an API client backed by the existing Python service.

## Future App Store Path

- Add a privacy policy that states no brokerage orders are placed by the app.
- Add configurable data refresh from the ETF Quant backend.
- Add account-independent paper portfolio state.
- Add risk disclaimers and avoid wording that implies guaranteed returns.
- Add TestFlight build, app icon, launch screen, and store screenshots.
