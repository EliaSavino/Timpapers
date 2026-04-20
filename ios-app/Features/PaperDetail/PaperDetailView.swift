import Charts
import SwiftUI

struct PaperDetailView: View {
    let title: String
    let authors: [String]
    let venue: String
    let year: Int
    let doiURL: URL?
    let openAlexURL: URL?
    let semanticScholarURL: URL?
    let citations: Int
    let badges: [String]
    let history: [CitationPointDTO]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text(title).font(.title3).bold()
                Text(authors.joined(separator: ", ")).font(.subheadline)
                Text("\(venue) · \(year)")
                    .foregroundStyle(.secondary)
                Text("\(citations) citations").font(.headline)

                ForEach(badges, id: \.self) {
                    Text($0).font(.caption).padding(8).background(.blue.opacity(0.12), in: Capsule())
                }

                Chart(history) {
                    LineMark(x: .value("Date", $0.date), y: .value("Citations", $0.totalCitations))
                }
                .frame(height: 220)

                Link("DOI", destination: doiURL ?? URL(string: "https://doi.org")!)
                if let openAlexURL { Link("OpenAlex", destination: openAlexURL) }
                if let semanticScholarURL { Link("Semantic Scholar", destination: semanticScholarURL) }
            }
            .padding()
        }
    }
}
