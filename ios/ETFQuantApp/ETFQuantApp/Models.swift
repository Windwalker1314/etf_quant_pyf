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
    let creator: String
    let isVerified: Bool
    var isSubscribed: Bool
    let monthlyPrice: Int
    let subscriberCount: Int
    let trustScore: Int
    let creatorBio: String
    let verificationItems: [String]
    let fit: String
    let subtitle: String
    let annualReturn: Double
    let maxDrawdown: Double
    let sharpe: Double
    let volatility: Double
    let latestSignal: String
    let plainSummary: String
    let principle: String
    let deliverables: [String]
    let riskNote: String
    let riskItems: [String]
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

enum RiskPreference: String, CaseIterable, Identifiable {
    case conservative
    case balanced
    case growth

    var id: String { rawValue }

    var title: String {
        switch self {
        case .conservative:
            return "Conservative"
        case .balanced:
            return "Balanced"
        case .growth:
            return "Growth"
        }
    }
}

struct InvestorProfile {
    var capital: Double
    var risk: RiskPreference
}
