import Foundation

@MainActor
final class AppStore: ObservableObject {
    @Published var strategies: [Strategy]
    @Published var selectedStrategyID: String
    @Published var reminder = ReminderState(hour: 9, minute: 20, notificationsEnabled: false)
    @Published var profile = InvestorProfile(capital: 100_000, risk: .balanced)
    @Published var notificationStatusText = "Notifications not configured"

    private let repository = DemoStrategyRepository()
    private let scheduler = NotificationScheduler()

    init() {
        let loaded = repository.loadStrategies()
        strategies = loaded
        selectedStrategyID = loaded.first?.id ?? ""
    }

    var selectedStrategy: Strategy {
        strategies.first { $0.id == selectedStrategyID } ?? strategies[0]
    }

    var subscribedCount: Int {
        strategies.filter(\.isSubscribed).count
    }

    func subscribeSelectedStrategy() {
        guard let index = strategies.firstIndex(where: { $0.id == selectedStrategyID }) else {
            return
        }
        strategies[index].isSubscribed = true
    }

    var recommendedStrategy: Strategy {
        let id: String
        switch profile.risk {
        case .conservative:
            id = "income_balance"
        case .balanced:
            id = "global_macro_risk"
        case .growth:
            id = "bigquant_rotation"
        }
        return strategies.first { $0.id == id } ?? selectedStrategy
    }

    var recommendationReason: String {
        switch profile.risk {
        case .conservative:
            return "\(recommendedStrategy.name) has lower drawdown and calmer turnover, which fits a conservative first subscription."
        case .balanced:
            return "\(recommendedStrategy.name) balances return and drawdown, making it a good default recommendation."
        case .growth:
            return "\(recommendedStrategy.name) has stronger return potential, with higher volatility to accept."
        }
    }

    func applyRecommendation() {
        selectedStrategyID = recommendedStrategy.id
    }

    func updateReminder(date: Date) {
        let components = Calendar.current.dateComponents([.hour, .minute], from: date)
        reminder.hour = components.hour ?? reminder.hour
        reminder.minute = components.minute ?? reminder.minute
    }

    func scheduleReminder() async {
        do {
            try await scheduler.scheduleDailyReminder(hour: reminder.hour, minute: reminder.minute)
            reminder.notificationsEnabled = true
            notificationStatusText = "Daily reminder scheduled at \(reminder.formattedTime)"
        } catch {
            reminder.notificationsEnabled = false
            notificationStatusText = error.localizedDescription
        }
    }
}
