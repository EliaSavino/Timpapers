import Charts
import SwiftUI

@MainActor
final class HIndexAnalysisViewModel: ObservableObject {
    @Published var analysis: HIndexAnalysisDTO?

    private let api: APIClientProtocol
    private let settings: AppSettings

    init(settings: AppSettings, api: APIClientProtocol? = nil) {
        self.settings = settings
        self.api = api ?? APIClient(baseURLProvider: settings)
    }

    func load() async {
        analysis = try? await api.fetchHIndex(authorID: settings.authorID)
    }
}

struct HIndexAnalysisView: View {
    @StateObject var viewModel: HIndexAnalysisViewModel

    var body: some View {
        ScrollView {
            if let analysis = viewModel.analysis {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Current h-index: \(analysis.hIndex)").font(.title2).bold()
                    Text("Papers 1...h are highlighted as contributors; near misses are closest to lifting h-index.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    Chart(analysis.rankedPapers) { item in
                        BarMark(
                            x: .value("Rank", item.rank),
                            y: .value("Citations", item.citations)
                        )
                        .foregroundStyle(color(for: item.group))

                        RuleMark(y: .value("Threshold", analysis.threshold))
                            .foregroundStyle(.red)
                            .lineStyle(StrokeStyle(lineWidth: 2, dash: [6]))
                    }
                    .frame(height: 260)

                    Text("Closest papers to increasing h-index").font(.headline)
                    ForEach(analysis.nearMisses.prefix(10)) { item in
                        Text("• \(item.title): needs \(item.deltaToNextH) citations")
                    }
                }
                .padding()
            }
        }
        .navigationTitle("H-Index Analysis")
        .task { await viewModel.load() }
    }

    private func color(for group: String) -> Color {
        switch group {
        case "contributor": return .green
        case "safe": return .blue
        case "near_miss": return .orange
        default: return .gray
        }
    }
}
