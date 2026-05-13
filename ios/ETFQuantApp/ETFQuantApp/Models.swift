import Foundation

enum TradeSide: String, CaseIterable, Identifiable {
    case buy = "BUY"
    case sell = "SELL"
    case hold = "HOLD"

    var id: String { rawValue }
}

struct BacktestPoint: Identifiable {
    let id = UUID()
    let date: Date
    let strategyValue: Double
    let baselineValue: Double
}

struct Allocation: Identifiable {
    let id = UUID()
    let symbol: String
    let name: String
    let weight: Double
}

struct RebalanceOrder: Identifiable {
    let id = UUID()
    let symbol: String
    let name: String
    let side: TradeSide
    let shares: Int
    let estimatedValue: Double
    let targetWeight: Double
}

struct Strategy: Identifiable {
    let id: String
    let name: String
    let subtitle: String
    let annualReturn: Double
    let maxDrawdown: Double
    let sharpe: Double
    let volatility: Double
    let latestSignal: String
    let riskNote: String
    let allocation: [Allocation]
    let orders: [RebalanceOrder]
    let curve: [BacktestPoint]
}

struct ReminderState {
    var hour: Int
    var minute: Int
    var notificationsEnabled: Bool

    var formattedTime: String {
        String(format: "%02d:%02d", hour, minute)
    }
}
