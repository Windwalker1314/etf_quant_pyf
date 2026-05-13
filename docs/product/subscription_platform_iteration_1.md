# ETF Quant Subscription Platform PRD - Iteration 1

## Product Goal

ETF Quant should help non-quant users subscribe to understandable ETF strategies and follow daily rebalance plans with confidence. It should also help professional strategy developers publish strategies, earn subscription revenue, and let the platform collect a marketplace fee.

## Personas

- Subscriber: does not understand quant modeling, but wants a disciplined ETF allocation product with clear return, drawdown, risk, and daily action guidance.
- Creator: understands strategy research, wants to publish a strategy, show verified backtest results, and monetize through subscriptions.
- Platform operator: reviews strategies, standardizes disclosure, handles marketplace discovery, reminders, and revenue share.

## Current Demo Gaps

- It shows strategy metrics, but does not answer "Should I pay for this?"
- It does not explain strategy logic in beginner language.
- It lacks marketplace packaging: price, creator, subscriber count, platform fee, and trust markers.
- It lacks a creator publishing flow.
- The daily rebalance view is useful, but should feel like a subscriber's operating cockpit.

## Iteration 1 Scope

1. Subscriber marketplace
   - Add an Explore tab with strategy cards.
   - Each card shows price, creator, verified status, annualized return, max drawdown, Sharpe, subscriber count, and a plain-language fit label.
   - Support selecting a strategy and simulating subscription.

2. Strategy detail page
   - Explain the strategy principle in beginner-friendly language.
   - Show what the user receives after subscribing.
   - Show key risks and when the strategy may underperform.
   - Keep backtest curve and target allocation visible.

3. Subscriber cockpit
   - Today view should emphasize subscription status, next reminder, latest signal, and concrete rebalance actions.
   - Add a "copy plan" simulation so the user feels the plan is actionable.

4. Creator studio
   - Add a creator-facing tab that previews publish requirements.
   - Show platform fee and creator estimated monthly revenue.
   - Include review checklist: data source, backtest, risk disclosure, and rebalance frequency.

5. Trust and compliance baseline
   - Copy should avoid implying guaranteed returns.
   - UI should say backtest is historical and does not guarantee future results.
   - Keep brokerage execution outside the demo.

## Acceptance Criteria

- A first-time user can understand what a strategy does within 60 seconds.
- A first-time user can identify price, return, risk, and next rebalance action without reading docs.
- A strategy developer can understand what is needed to publish.
- The platform business model is visible through a fee/revenue share section.
- The local browser demo remains runnable without Xcode.
- SwiftUI demo keeps matching data structures for future native development.

## Customer Assessment After Iteration 1

Expected result: improved willingness to try because the app now communicates value, trust, and action. Still likely not enough for real payment until live data, audited backtests, creator identity, and trial/subscription mechanics are implemented.
