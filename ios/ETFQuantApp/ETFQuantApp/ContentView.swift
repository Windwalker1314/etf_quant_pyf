import Charts
import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        TabView {
            TodayView()
                .tabItem {
                    Label("Today", systemImage: "sun.max")
                }

            StrategiesView()
                .tabItem {
                    Label("Strategies", systemImage: "square.stack.3d.up")
                }

            BacktestView()
                .tabItem {
                    Label("Backtest", systemImage: "chart.xyaxis.line")
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
                    ReminderBanner()
                    OrdersSection(strategy: store.selectedStrategy)
                }
                .padding()
            }
            .background(Color.appGroupedBackground)
            .navigationTitle("ETF Quant")
        }
    }
}

struct StrategiesView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        NavigationStack {
            List {
                Section("Strategy") {
                    Picker("Selected strategy", selection: $store.selectedStrategyID) {
                        ForEach(store.strategies) { strategy in
                            Text(strategy.name).tag(strategy.id)
                        }
                    }
                }

                Section("Allocation") {
                    ForEach(store.selectedStrategy.allocation) { item in
                        AllocationRow(allocation: item)
                    }
                }

                Section("Risk note") {
                    Text(store.selectedStrategy.riskNote)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Strategies")
        }
    }
}

struct BacktestView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    ChartCard(strategy: store.selectedStrategy)
                    MetricsStrip(strategy: store.selectedStrategy)
                    SignalCard(strategy: store.selectedStrategy)
                }
                .padding()
            }
            .background(Color.appGroupedBackground)
            .navigationTitle("Backtest")
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

struct StrategyHeader: View {
    let strategy: Strategy

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(strategy.name)
                .font(.title.bold())
            Text(strategy.subtitle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text(strategy.latestSignal)
                .font(.headline)
                .foregroundStyle(.teal)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

struct MetricsStrip: View {
    let strategy: Strategy

    var body: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 10), count: 2), spacing: 10) {
            MetricTile(title: "Annualized", value: strategy.annualReturn.percentText)
            MetricTile(title: "Max DD", value: strategy.maxDrawdown.percentText)
            MetricTile(title: "Sharpe", value: String(format: "%.2f", strategy.sharpe))
            MetricTile(title: "Volatility", value: strategy.volatility.percentText)
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
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
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
        .padding()
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
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
        .padding()
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
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
            Text(strategy.name)
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
            .frame(height: 240)
        }
        .padding()
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

struct SignalCard: View {
    let strategy: Strategy

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Latest Signal")
                .font(.headline)
            Text(strategy.latestSignal)
                .foregroundStyle(.primary)
            Text(strategy.riskNote)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
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
