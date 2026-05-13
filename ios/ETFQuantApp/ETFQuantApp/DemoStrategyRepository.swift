import Foundation

struct DemoStrategyRepository {
    func loadStrategies() -> [Strategy] {
        [
            rotationStrategy(),
            macroRiskStrategy(),
            equalWeightStrategy()
        ]
    }

    private func rotationStrategy() -> Strategy {
        Strategy(
            id: "bigquant_rotation",
            name: "PYF ETF Rotation",
            creator: "PYF Research",
            isVerified: true,
            isSubscribed: true,
            monthlyPrice: 59,
            subscriberCount: 1286,
            trustScore: 92,
            creatorBio: "Focuses on ETF rotation and out-of-sample validation. Maintains the core strategy library for this project.",
            verificationItems: ["Backtest reproduced", "Walk-forward passed", "Live signal tracking for 63 days", "Latest review: 2026-05-12"],
            fit: "For users who want active ETF rotation",
            subtitle: "Trend momentum plus volatility filtering across A-share, gold, overseas index, and bond ETFs.",
            annualReturn: 0.184,
            maxDrawdown: -0.116,
            sharpe: 1.34,
            volatility: 0.138,
            latestSignal: "Risk-on, gold and broad-market beta are leading",
            plainSummary: "Checks ETF trend and stability, then sends the next trading day's target allocation.",
            principle: "The strategy ranks ETFs by recent trend strength and penalizes unstable moves. It prefers assets with stronger momentum and controlled volatility, then raises bond exposure when market conditions weaken.",
            deliverables: ["Daily rebalance reminder", "Target weights and trade direction", "Backtest curve", "Failure scenario notes"],
            riskNote: "Higher turnover. Confirm liquidity before market open.",
            riskItems: ["Choppy markets can increase turnover", "May lag a single strong index over short windows", "QDII ETFs can be affected by FX and quota constraints"],
            allocation: [
                Allocation(symbol: "518880.SH", name: "Gold ETF", weight: 0.35),
                Allocation(symbol: "510300.SH", name: "CSI 300 ETF", weight: 0.30),
                Allocation(symbol: "513100.SH", name: "Nasdaq ETF", weight: 0.20),
                Allocation(symbol: "511010.SH", name: "Treasury ETF", weight: 0.15)
            ],
            orders: [
                RebalanceOrder(symbol: "518880.SH", name: "Gold ETF", side: .buy, shares: 2000, estimatedValue: 10480, targetWeight: 0.35),
                RebalanceOrder(symbol: "513100.SH", name: "Nasdaq ETF", side: .sell, shares: 800, estimatedValue: 7264, targetWeight: 0.20),
                RebalanceOrder(symbol: "511010.SH", name: "Treasury ETF", side: .hold, shares: 0, estimatedValue: 0, targetWeight: 0.15)
            ],
            curve: makeCurve(seed: 0.18, drawdown: 0.08)
        )
    }

    private func macroRiskStrategy() -> Strategy {
        Strategy(
            id: "global_macro_risk",
            name: "Global Macro Risk",
            creator: "Northstar Macro",
            isVerified: true,
            isSubscribed: false,
            monthlyPrice: 79,
            subscriberCount: 842,
            trustScore: 88,
            creatorBio: "Macro allocation research team focused on drawdown control and defensive portfolios.",
            verificationItems: ["Data source reviewed", "Out-of-sample curve submitted", "Live signal tracking for 41 days", "Latest review: 2026-05-10"],
            fit: "For users who care most about drawdown control",
            subtitle: "Macro risk regime allocation across equity, gold, and bond ETFs.",
            annualReturn: 0.128,
            maxDrawdown: -0.082,
            sharpe: 1.18,
            volatility: 0.095,
            latestSignal: "Neutral risk, keep a balanced defensive mix",
            plainSummary: "Reduces equity exposure when risk rises and restores it when conditions improve.",
            principle: "The strategy maps the market into risk-on, neutral, and risk-off regimes. It is designed to avoid large drawdowns first, then participate when the risk backdrop improves.",
            deliverables: ["Daily risk regime update", "Defensive and offensive allocation", "Macro indicator explanation", "Monthly strategy review"],
            riskNote: "Lower turnover. May lag during fast equity rallies.",
            riskItems: ["Can lag in strong bull markets", "Macro signals may be late", "Defensive assets can also decline"],
            allocation: [
                Allocation(symbol: "511010.SH", name: "Treasury ETF", weight: 0.40),
                Allocation(symbol: "518880.SH", name: "Gold ETF", weight: 0.25),
                Allocation(symbol: "510300.SH", name: "CSI 300 ETF", weight: 0.20),
                Allocation(symbol: "513100.SH", name: "Nasdaq ETF", weight: 0.15)
            ],
            orders: [
                RebalanceOrder(symbol: "511010.SH", name: "Treasury ETF", side: .buy, shares: 1200, estimatedValue: 12600, targetWeight: 0.40),
                RebalanceOrder(symbol: "510300.SH", name: "CSI 300 ETF", side: .hold, shares: 0, estimatedValue: 0, targetWeight: 0.20)
            ],
            curve: makeCurve(seed: 0.12, drawdown: 0.05)
        )
    }

    private func equalWeightStrategy() -> Strategy {
        Strategy(
            id: "income_balance",
            name: "Income Balance ETF",
            creator: "Harbor Quant Lab",
            isVerified: false,
            isSubscribed: false,
            monthlyPrice: 39,
            subscriberCount: 312,
            trustScore: 71,
            creatorBio: "New strategy team focused on low-volatility ETF allocation.",
            verificationItems: ["Backtest submitted", "Full out-of-sample review pending", "Live signal tracking for 12 days", "Latest review: 2026-05-08"],
            fit: "For beginners who want a calmer ETF portfolio",
            subtitle: "Low-turnover allocation strategy centered on bonds and gold.",
            annualReturn: 0.092,
            maxDrawdown: -0.071,
            sharpe: 0.91,
            volatility: 0.082,
            latestSignal: "Stay defensive and wait for equity trend confirmation",
            plainSummary: "A slower asset allocation strategy for users who prefer fewer trades.",
            principle: "The strategy keeps most exposure in bonds and gold, then gradually adds equity ETFs only when trends improve. It gives up some upside for a smoother holding experience.",
            deliverables: ["Weekly allocation check", "Low-frequency rebalance alerts", "Beginner-friendly signal explanation", "Portfolio risk temperature"],
            riskNote: "Lower volatility does not mean no losses.",
            riskItems: ["Limited upside in fast rallies", "Can still lose money", "Not suitable for short-term speculation"],
            allocation: [
                Allocation(symbol: "518880.SH", name: "Gold ETF", weight: 0.25),
                Allocation(symbol: "510300.SH", name: "CSI 300 ETF", weight: 0.15),
                Allocation(symbol: "159915.SZ", name: "ChiNext ETF", weight: 0.10),
                Allocation(symbol: "511010.SH", name: "Treasury ETF", weight: 0.50)
            ],
            orders: [
                RebalanceOrder(symbol: "518880.SH", name: "Gold ETF", side: .hold, shares: 0, estimatedValue: 0, targetWeight: 0.25)
            ],
            curve: makeCurve(seed: 0.08, drawdown: 0.12)
        )
    }

    private func makeCurve(seed: Double, drawdown: Double) -> [BacktestPoint] {
        let calendar = Calendar(identifier: .gregorian)
        let start = calendar.date(from: DateComponents(year: 2023, month: 1, day: 1)) ?? Date()

        return (0..<24).compactMap { month in
            guard let date = calendar.date(byAdding: .month, value: month, to: start) else {
                return nil
            }
            let wave = sin(Double(month) / 2.4) * drawdown
            let trend = 1.0 + seed * Double(month) / 12.0
            let baselineTrend = 1.0 + 0.075 * Double(month) / 12.0
            return BacktestPoint(
                date: date,
                strategyValue: trend + wave,
                baselineValue: baselineTrend + sin(Double(month) / 2.1) * 0.045
            )
        }
    }
}
