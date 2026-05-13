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
            subtitle: "Momentum plus volatility rotation across A-share and commodity ETFs",
            annualReturn: 0.184,
            maxDrawdown: -0.116,
            sharpe: 1.34,
            volatility: 0.138,
            latestSignal: "Risk-on, rotate to gold and broad-market beta",
            riskNote: "Higher turnover. Confirm liquidity before market open.",
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
            subtitle: "Risk regime allocation with defensive bond and gold sleeves",
            annualReturn: 0.128,
            maxDrawdown: -0.082,
            sharpe: 1.18,
            volatility: 0.095,
            latestSignal: "Neutral risk, keep a balanced defensive mix",
            riskNote: "Lower turnover. May lag during fast equity rallies.",
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
            id: "equal_weight",
            name: "Equal Weight Baseline",
            subtitle: "Simple benchmark allocation for sanity checks",
            annualReturn: 0.092,
            maxDrawdown: -0.151,
            sharpe: 0.74,
            volatility: 0.126,
            latestSignal: "No signal. Maintain equal weights.",
            riskNote: "Useful as a baseline, not an adaptive strategy.",
            allocation: [
                Allocation(symbol: "518880.SH", name: "Gold ETF", weight: 0.25),
                Allocation(symbol: "510300.SH", name: "CSI 300 ETF", weight: 0.25),
                Allocation(symbol: "513100.SH", name: "Nasdaq ETF", weight: 0.25),
                Allocation(symbol: "511010.SH", name: "Treasury ETF", weight: 0.25)
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
