import Foundation

@MainActor
final class AppStore: ObservableObject {
    @Published var strategies: [Strategy]
    @Published var selectedStrategyID: String
    @Published var reminder = ReminderState(hour: 9, minute: 20, notificationsEnabled: false)
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
