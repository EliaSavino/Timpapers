import SwiftUI

@main
struct TimPapersApp: App {
    @StateObject private var settings = AppSettings()

    var body: some Scene {
        WindowGroup {
            RootTabView()
                .environmentObject(settings)
        }
    }
}

struct RootTabView: View {
    @EnvironmentObject private var settings: AppSettings

    var body: some View {
        TabView {
            DashboardView(viewModel: DashboardViewModel(settings: settings))
                .tabItem { Label("Dashboard", systemImage: "rectangle.grid.2x2") }
            PapersListView(viewModel: PapersViewModel(settings: settings))
                .tabItem { Label("Papers", systemImage: "doc.text") }
            HIndexAnalysisView(viewModel: HIndexAnalysisViewModel(settings: settings))
                .tabItem { Label("H-Index", systemImage: "chart.bar") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}
