import Foundation

enum WidgetSync {
    static func persistFromDashboard(_ dashboard: DashboardDTO, suiteName: String = "group.com.example.timpapers") {
        let snapshot = WidgetSnapshot(
            hIndex: dashboard.hIndex,
            totalCitations: dashboard.totalCitations,
            gain7d: dashboard.gain7d,
            topMoverTitle: dashboard.fastestGrowing.first?.title ?? "No data"
        )
        if let data = try? JSONEncoder().encode(snapshot) {
            UserDefaults(suiteName: suiteName)?.set(data, forKey: "widget_snapshot")
        }
    }
}
