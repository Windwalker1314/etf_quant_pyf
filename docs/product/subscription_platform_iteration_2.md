# ETF Quant Subscription Platform PRD - Iteration 2

## Product Question

Would a beginner understand which strategy to subscribe to and how much money the daily plan applies to?

## Customer Finding From Iteration 1

The marketplace and strategy details communicate value better, but a non-quant user still has to self-select. That creates hesitation before payment. The app needs a simple investor profile, recommendation reason, and capital-based plan.

## Iteration 2 Scope

1. Beginner profile
   - Ask for investable capital.
   - Ask for risk preference: conservative, balanced, or growth.
   - Store the profile locally in the demo.

2. Strategy recommendation
   - Recommend one strategy based on risk preference.
   - Explain why the strategy matches the user.
   - Let the user apply the recommendation.

3. Capital-aware cockpit
   - Show the capital amount on Today.
   - Scale target allocation values by capital.
   - Make daily plan feel directly actionable.

4. Paid conversion
   - Add a trial-oriented subscription CTA.
   - Show why the user is paying: daily signal, allocation, risk warning, and backtest tracking.

## Acceptance Criteria

- A beginner can enter capital and risk preference in Settings.
- Explore shows a recommended strategy and reason.
- Today shows target values based on the user's capital.
- The subscribe CTA feels less abrupt because it is tied to a personalized recommendation.
