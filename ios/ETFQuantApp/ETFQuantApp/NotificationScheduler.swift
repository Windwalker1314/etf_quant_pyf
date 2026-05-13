import Foundation
import UserNotifications

enum NotificationSchedulerError: LocalizedError {
    case permissionDenied

    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "Notification permission was not granted."
        }
    }
}

struct NotificationScheduler {
    private let center = UNUserNotificationCenter.current()

    func scheduleDailyReminder(hour: Int, minute: Int) async throws {
        let granted = try await center.requestAuthorization(options: [.alert, .badge, .sound])
        guard granted else {
            throw NotificationSchedulerError.permissionDenied
        }

        center.removePendingNotificationRequests(withIdentifiers: ["daily-rebalance-reminder"])

        let content = UNMutableNotificationContent()
        content.title = "ETF Quant rebalance check"
        content.body = "Review today's strategy signal and target allocation before trading."
        content.sound = .default

        var dateComponents = DateComponents()
        dateComponents.hour = hour
        dateComponents.minute = minute

        let trigger = UNCalendarNotificationTrigger(dateMatching: dateComponents, repeats: true)
        let request = UNNotificationRequest(identifier: "daily-rebalance-reminder", content: content, trigger: trigger)
        try await center.add(request)
    }
}
