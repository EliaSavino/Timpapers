import Charts
import SwiftUI
import WidgetKit

@MainActor
final class DashboardViewModel: ObservableObject {
    @Published var dashboard: DashboardDTO?
    @Published var errorMessage: String?

    private let api: APIClientProtocol
    private let cache: CacheStore
    private let settings: AppSettings

    init(settings: AppSettings, api: APIClientProtocol? = nil, cache: CacheStore = AppCache()) {
        self.settings = settings
        self.api = api ?? APIClient(baseURLProvider: settings)
        self.cache = cache
        self.dashboard = cache.loadDashboard()
    }

    func refresh() async {
        do {
            let payload = try await api.fetchDashboard(authorID: settings.authorID)
            dashboard = payload
            cache.saveDashboard(payload)
            WidgetSync.persistFromDashboard(payload)
            WidgetCenter.shared.reloadAllTimelines()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

struct DashboardView: View {
    @StateObject var viewModel: DashboardViewModel

    private let columns = [GridItem(.flexible()), GridItem(.flexible())]

    var body: some View {
        NavigationStack {
            ScrollView {
                if let data = viewModel.dashboard {
                    LazyVGrid(columns: columns) {
                        MetricCard(title: "Citations", value: "\(data.totalCitations)")
                        MetricCard(title: "h-index", value: "\(data.hIndex)")
                        MetricCard(title: "i10-index", value: "\(data.i10Index)")
                        MetricCard(title: "Papers", value: "\(data.totalPapers)")
                    }
                    Chart(data.growth) {
                        LineMark(x: .value("Date", $0.date), y: .value("Citations", $0.totalCitations))
                    }
                    .frame(height: 220)

                    VStack(alignment: .leading) {
                        Text("Top cited")
                        ForEach(data.topCited.prefix(5)) { paper in
                            Text("• \(paper.title) (\(paper.citations))")
                        }
                        Text("Fastest growing")
                            .padding(.top)
                        ForEach(data.fastestGrowing.prefix(5)) { paper in
                            Text("• \(paper.title) (+\(paper.citationGain30d))")
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .padding()
            .navigationTitle("Dashboard")
            .task { await viewModel.refresh() }
            .refreshable { await viewModel.refresh() }
        }
    }
}

private struct MetricCard: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.title2).bold()
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}
