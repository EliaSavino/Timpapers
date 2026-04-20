import SwiftUI
import WidgetKit

struct WidgetSnapshot: Codable {
    let hIndex: Int
    let totalCitations: Int
    let gain7d: Int
    let topMoverTitle: String
}

struct TimPapersEntry: TimelineEntry {
    let date: Date
    let snapshot: WidgetSnapshot
}

struct TimPapersProvider: TimelineProvider {
    private let suite = UserDefaults(suiteName: "group.com.example.timpapers")

    func placeholder(in context: Context) -> TimPapersEntry {
        TimPapersEntry(date: .now, snapshot: .init(hIndex: 12, totalCitations: 1530, gain7d: 18, topMoverTitle: "Example Paper"))
    }

    func getSnapshot(in context: Context, completion: @escaping (TimPapersEntry) -> Void) {
        completion(loadEntry())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<TimPapersEntry>) -> Void) {
        let entry = loadEntry()
        let timeline = Timeline(entries: [entry], policy: .after(Date().addingTimeInterval(60 * 60)))
        completion(timeline)
    }

    private func loadEntry() -> TimPapersEntry {
        guard
            let data = suite?.data(forKey: "widget_snapshot"),
            let snapshot = try? JSONDecoder().decode(WidgetSnapshot.self, from: data)
        else {
            return placeholder(in: .init())
        }
        return TimPapersEntry(date: .now, snapshot: snapshot)
    }
}

struct TimPapersWidgetEntryView: View {
    var entry: TimPapersProvider.Entry
    @Environment(\.widgetFamily) private var family

    var body: some View {
        switch family {
        case .systemSmall:
            VStack(alignment: .leading) {
                Text("h-index \(entry.snapshot.hIndex)").font(.headline)
                Text("\(entry.snapshot.totalCitations) cites").font(.subheadline)
                Text("+\(entry.snapshot.gain7d) (7d)").font(.caption)
            }
        case .systemMedium:
            HStack {
                VStack(alignment: .leading) {
                    Text("h-index \(entry.snapshot.hIndex)").font(.headline)
                    Text("Total \(entry.snapshot.totalCitations)")
                    Text("Top mover").font(.caption)
                    Text(entry.snapshot.topMoverTitle).lineLimit(2).font(.caption2)
                }
                Spacer()
                Image(systemName: "chart.line.uptrend.xyaxis")
            }
        default:
            Text("h \(entry.snapshot.hIndex)")
        }
    }
}

struct TimPapersWidget: Widget {
    let kind = "TimPapersWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: TimPapersProvider()) { entry in
            TimPapersWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("TimPapers Metrics")
        .description("Track h-index and citation momentum.")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryRectangular])
    }
}

@main
struct TimPapersWidgetBundle: WidgetBundle {
    var body: some Widget {
        TimPapersWidget()
    }
}
