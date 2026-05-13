import Charts
import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            TodayView()
                .tabItem {
                    Label("Today", systemImage: "sun.max")
                }

            ExploreView()
                .tabItem {
                    Label("Explore", systemImage: "storefront")
                }

            StrategyDetailView()
                .tabItem {
                    Label("Detail", systemImage: "doc.text.magnifyingglass")
                }

            CreatorStudioView()
                .tabItem {
                    Label("Studio", systemImage: "hammer")
                }

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape")
                }
        }
        .tint(.teal)
    }
}

struct TodayView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    StrategyHeader(strategy: store.selectedStrategy)
                    MetricsStrip(strategy: store.selectedStrategy)
                    MetricTile(title: "Plan Capital", value: store.profile.capital.currencyText)
                    ReminderBanner()
                    ChartCard(strategy: store.selectedStrategy)
                    OrdersSection(strategy: store.selectedStrategy)
                }
                .padding()
            }
            .background(Color.appGroupedBackground)
            .navigationTitle("ETF Quant")
        }
    }
}

struct ExploreView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    RecommendationCard()
                    ForEach(store.strategies) { strategy in
                        MarketplaceCard(strategy: strategy, isSelected: strategy.id == store.selectedStrategyID) {
                            store.selectedStrategyID = strategy.id
                        }
                    }
                }
                .padding()
            }
            .background(Color.appGroupedBackground)
            .navigationTitle("Explore")
        }
    }
}

struct StrategyDetailView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    SubscribeCard(strategy: store.selectedStrategy) {
                        store.subscribeSelectedStrategy()
                    }
                    TrustCard(strategy: store.selectedStrategy)
                    ExplanationCard(strategy: store.selectedStrategy)
                    ChartCard(strategy: store.selectedStrategy)
                    AllocationSection(strategy: store.selectedStrategy)
                    RiskSection(strategy: store.selectedStrategy)
                }
                .padding()
            }
            .background(Color.appGroupedBackground)
            .navigationTitle("Detail")
        }
    }
}

struct TrustCard: View {
    let strategy: Strategy

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading) {
                    Text("Trust score")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("\(strategy.trustScore)")
                        .font(.largeTitle.bold())
                        .foregroundStyle(.teal)
                }
                Spacer()
                Text(strategy.isVerified ? "Platform reviewed" : "Review pending")
                    .font(.caption.bold())
                    .foregroundStyle(strategy.isVerified ? .green : .secondary)
            }
            Text(strategy.creatorBio)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            ChecklistContent(items: strategy.verificationItems)
        }
        .cardStyle()
    }
}

struct CreatorStudioView: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Publish your strategy")
                            .font(.title2.bold())
                        Text("Upload the strategy explanation, reproducible backtest, rebalance frequency, and risk disclosure. The platform handles discovery, subscriptions, reminders, and signal delivery.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Text("Platform fee 20% / Creator share 80%")
                            .font(.headline)
                            .foregroundStyle(.teal)
                    }
                    .cardStyle()

                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 10), count: 2), spacing: 10) {
                        MetricTile(title: "Example Price", value: "CNY 99")
                        MetricTile(title: "Subscribers", value: "300")
                        MetricTile(title: "Platform", value: "CNY 5,940")
                        MetricTile(title: "Creator", value: "CNY 23,760")
                    }

                    ChecklistCard(
                        title: "Review checklist",
                        items: [
                            "Reproducible config and out-of-sample curve",
                            "Plain-language strategy explanation",
                            "Drawdown, turnover, and failure scenarios",
                            "Daily or weekly signal delivery interface"
                        ]
                    )
                }
                .padding()
            }
            .background(Color.appGroupedBackground)
            .navigationTitle("Studio")
        }
    }
}

struct SettingsView: View {
    @EnvironmentObject private var store: AppStore

    private var reminderBinding: Binding<Date> {
        Binding {
            Calendar.current.date(from: DateComponents(hour: store.reminder.hour, minute: store.reminder.minute)) ?? Date()
        } set: { newValue in
            store.updateReminder(date: newValue)
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Daily rebalance reminder") {
                    TextField("Plan capital", value: $store.profile.capital, format: .number)
                    Picker("Risk preference", selection: $store.profile.risk) {
                        ForEach(RiskPreference.allCases) { risk in
                            Text(risk.title).tag(risk)
                        }
                    }
                    DatePicker("Reminder time", selection: reminderBinding, displayedComponents: .hourAndMinute)

                    Button {
                        Task {
                            await store.scheduleReminder()
                        }
                    } label: {
                        Label("Schedule daily reminder", systemImage: "bell.badge")
                    }

                    Text(store.notificationStatusText)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Account") {
                    Text("Subscribed strategies: \(store.subscribedCount)")
                    Text("Broker execution is outside this demo. Backtests do not guarantee future returns.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Data connection") {
                    Label("Demo data is embedded", systemImage: "externaldrive")
                    Text("Next step: connect this boundary to the existing Python ETF Quant service.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
        }
    }
}

struct RecommendationCard: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Recommended for \(store.profile.risk.title)")
                    .font(.headline)
                Spacer()
                Text(store.profile.capital.currencyText)
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
            }
            Text(store.recommendationReason)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button("Use recommended strategy") {
                store.applyRecommendation()
            }
            .buttonStyle(.borderedProminent)
            .tint(.teal)
        }
        .cardStyle()
    }
}

struct StrategyHeader: View {
    let strategy: Strategy

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(strategy.isSubscribed ? "Subscribed" : "Not subscribed")
                    .font(.caption.bold())
                    .foregroundStyle(strategy.isSubscribed ? .green : .secondary)
                Spacer()
                Text("CNY \(strategy.monthlyPrice)/mo")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
            }
            Text(strategy.name)
                .font(.title.bold())
            Text(strategy.subtitle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text(strategy.latestSignal)
                .font(.headline)
                .foregroundStyle(.teal)
            Text(strategy.plainSummary)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .cardStyle()
    }
}

struct MetricsStrip: View {
    let strategy: Strategy

    var body: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 10), count: 2), spacing: 10) {
            MetricTile(title: "Annualized", value: strategy.annualReturn.percentText)
            MetricTile(title: "Max DD", value: strategy.maxDrawdown.percentText)
            MetricTile(title: "Sharpe", value: String(format: "%.2f", strategy.sharpe))
            MetricTile(title: "Monthly", value: "CNY \(strategy.monthlyPrice)")
        }
    }
}

struct MetricTile: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title3.bold())
                .minimumScaleFactor(0.75)
        }
        .cardStyle()
    }
}

struct ReminderBanner: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: store.reminder.notificationsEnabled ? "bell.badge.fill" : "bell")
                .font(.title2)
                .foregroundStyle(.teal)
            VStack(alignment: .leading, spacing: 3) {
                Text("Daily rebalance reminder")
                    .font(.headline)
                Text("Next check at \(store.reminder.formattedTime)")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .cardStyle()
    }
}

struct MarketplaceCard: View {
    let strategy: Strategy
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text(strategy.isVerified ? "Verified" : "Pending")
                        .font(.caption.bold())
                        .foregroundStyle(strategy.isVerified ? .green : .secondary)
                    Spacer()
                    Text("CNY \(strategy.monthlyPrice)/mo")
                        .font(.caption.bold())
                        .foregroundStyle(.secondary)
                }
                Text(strategy.name)
                    .font(.headline)
                    .foregroundStyle(.primary)
                Text(strategy.fit)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                HStack {
                    Text(strategy.annualReturn.percentText)
                    Text(strategy.maxDrawdown.percentText)
                    Text("\(strategy.subscriberCount) subscribers")
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }
            .padding()
            .background(.background)
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(isSelected ? Color.teal : Color.clear, lineWidth: 2)
            )
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

struct SubscribeCard: View {
    let strategy: Strategy
    let onSubscribe: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(strategy.creator)
                .font(.caption.bold())
                .foregroundStyle(.secondary)
            Text(strategy.fit)
                .font(.title3.bold())
            Text(strategy.subtitle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button(action: onSubscribe) {
                Label(strategy.isSubscribed ? "Subscribed" : "Subscribe CNY \(strategy.monthlyPrice)/mo", systemImage: "checkmark.seal")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.teal)
        }
        .cardStyle()
    }
}

struct ExplanationCard: View {
    let strategy: Strategy

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Strategy principle")
                .font(.headline)
            Text(strategy.principle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            ChecklistContent(items: strategy.deliverables)
        }
        .cardStyle()
    }
}

struct OrdersSection: View {
    let strategy: Strategy

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Rebalance Plan")
                .font(.headline)
            ForEach(strategy.orders) { order in
                OrderRow(order: order)
            }
        }
        .cardStyle()
    }
}

struct OrderRow: View {
    let order: RebalanceOrder

    var body: some View {
        HStack(spacing: 12) {
            Text(order.side.rawValue)
                .font(.caption.bold())
                .foregroundStyle(order.side == .sell ? .red : order.side == .buy ? .green : .secondary)
                .frame(width: 44, alignment: .leading)
            VStack(alignment: .leading, spacing: 2) {
                Text(order.symbol)
                    .font(.subheadline.bold())
                Text(order.name)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text(order.targetWeight.percentText)
                    .font(.subheadline.bold())
                Text(order.estimatedValue.currencyText)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 6)
    }
}

struct AllocationSection: View {
    let strategy: Strategy

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Target allocation")
                .font(.headline)
            ForEach(strategy.allocation) { item in
                AllocationRow(allocation: item)
            }
        }
        .cardStyle()
    }
}

struct AllocationRow: View {
    let allocation: Allocation

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading) {
                    Text(allocation.symbol)
                        .font(.subheadline.bold())
                    Text(allocation.name)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Text(allocation.weight.percentText)
                    .font(.headline)
            }
            ProgressView(value: allocation.weight)
                .tint(.teal)
        }
        .padding(.vertical, 4)
    }
}

struct ChartCard: View {
    let strategy: Strategy

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Backtest curve")
                .font(.headline)
            Chart {
                ForEach(strategy.curve) { point in
                    LineMark(x: .value("Date", point.date), y: .value("Strategy", point.strategyValue))
                        .foregroundStyle(.teal)
                    LineMark(x: .value("Date", point.date), y: .value("Baseline", point.baselineValue))
                        .foregroundStyle(.orange)
                }
            }
            .chartYScale(domain: .automatic(includesZero: false))
            .frame(height: 220)
            Text("Historical backtests do not guarantee future returns. Slippage, fees, and execution price can affect results.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .cardStyle()
    }
}

struct RiskSection: View {
    let strategy: Strategy

    var body: some View {
        ChecklistCard(title: "Main risks", items: strategy.riskItems + [strategy.riskNote])
    }
}

struct ChecklistCard: View {
    let title: String
    let items: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            ChecklistContent(items: items)
        }
        .cardStyle()
    }
}

struct ChecklistContent: View {
    let items: [String]

    var body: some View {
        ForEach(items, id: \.self) { item in
            HStack(alignment: .top, spacing: 8) {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(.teal)
                Text(item)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private extension Double {
    var percentText: String {
        formatted(.percent.precision(.fractionLength(1)))
    }

    var currencyText: String {
        formatted(.currency(code: "CNY").precision(.fractionLength(0)))
    }
}

private extension Color {
    static let appGroupedBackground = Color(red: 0.94, green: 0.96, blue: 0.97)
}

private extension View {
    func cardStyle() -> some View {
        self
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
            .background(.background)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}
