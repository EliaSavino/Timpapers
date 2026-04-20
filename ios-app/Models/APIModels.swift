import Foundation

struct MetricsDTO: Codable {
    let totalCitations: Int
    let paperCount: Int
    let hIndex: Int
    let i10Index: Int
    let gain7d: Int
    let gain30d: Int
}

struct CitationPointDTO: Codable, Identifiable {
    let date: Date
    let totalCitations: Int
    var id: Date { date }
}

struct PaperSummaryDTO: Codable, Identifiable {
    let id: Int
    let title: String
    let year: Int?
    let venue: String?
    let citations: Int
    let citationGain30d: Int
    let contributesToHIndex: Bool
    let nearHThreshold: Bool
}

struct EventDTO: Codable, Identifiable {
    let id: Int
    let eventType: String
    let message: String
    let paperID: Int?
    let eventValue: Double?
    let createdAt: Date
}

struct DashboardDTO: Codable {
    let totalCitations: Int
    let hIndex: Int
    let i10Index: Int
    let totalPapers: Int
    let gain7d: Int
    let gain30d: Int
    let growth: [CitationPointDTO]
    let topCited: [PaperSummaryDTO]
    let fastestGrowing: [PaperSummaryDTO]
    let recentEvents: [EventDTO]
}

struct HIndexBinDTO: Codable, Identifiable {
    let paperID: Int
    let title: String
    let rank: Int
    let citations: Int
    let group: String
    let deltaToNextH: Int
    var id: Int { paperID }
}

struct HIndexAnalysisDTO: Codable {
    let hIndex: Int
    let threshold: Int
    let contributors: [HIndexBinDTO]
    let safeAboveThreshold: [HIndexBinDTO]
    let nearMisses: [HIndexBinDTO]
    let farBelow: [HIndexBinDTO]
    let rankedPapers: [HIndexBinDTO]
}
