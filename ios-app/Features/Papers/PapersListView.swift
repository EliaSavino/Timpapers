import SwiftUI

enum PaperSortMode: String, CaseIterable {
    case citations, growth, year, title
}

@MainActor
final class PapersViewModel: ObservableObject {
    @Published var papers: [PaperSummaryDTO] = []
    @Published var query: String = ""
    @Published var sortMode: PaperSortMode = .citations
    @Published var hContributorsOnly: Bool = false
    @Published var nearThresholdOnly: Bool = false

    private let api: APIClientProtocol
    private let settings: AppSettings

    init(settings: AppSettings, api: APIClientProtocol? = nil) {
        self.settings = settings
        self.api = api ?? APIClient(baseURLProvider: settings)
    }

    func load() async {
        papers = (try? await api.fetchPapers(authorID: settings.authorID)) ?? []
    }

    var filtered: [PaperSummaryDTO] {
        var values = papers.filter { query.isEmpty || $0.title.localizedCaseInsensitiveContains(query) }
        if hContributorsOnly { values = values.filter(\.contributesToHIndex) }
        if nearThresholdOnly { values = values.filter(\.nearHThreshold) }
        switch sortMode {
        case .citations: values.sort { $0.citations > $1.citations }
        case .growth: values.sort { $0.citationGain30d > $1.citationGain30d }
        case .year: values.sort { ($0.year ?? 0) > ($1.year ?? 0) }
        case .title: values.sort { $0.title < $1.title }
        }
        return values
    }
}

struct PapersListView: View {
    @StateObject var viewModel: PapersViewModel

    var body: some View {
        NavigationStack {
            List(viewModel.filtered) { paper in
                VStack(alignment: .leading) {
                    Text(paper.title).font(.headline)
                    Text("\(paper.citations) citations · +\(paper.citationGain30d) /30d")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .searchable(text: $viewModel.query)
            .toolbar {
                Menu("Sort") {
                    Picker("Sort", selection: $viewModel.sortMode) {
                        ForEach(PaperSortMode.allCases, id: \.rawValue) { mode in
                            Text(mode.rawValue.capitalized).tag(mode)
                        }
                    }
                }
                Toggle("H Contributors", isOn: $viewModel.hContributorsOnly)
                Toggle("Near Threshold", isOn: $viewModel.nearThresholdOnly)
            }
            .task { await viewModel.load() }
            .navigationTitle("Papers")
        }
    }
}
