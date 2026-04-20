import Foundation

protocol APIClientProtocol {
    func fetchDashboard(authorID: Int) async throws -> DashboardDTO
    func fetchPapers(authorID: Int) async throws -> [PaperSummaryDTO]
    func fetchMetrics(authorID: Int) async throws -> MetricsDTO
    func fetchHIndex(authorID: Int) async throws -> HIndexAnalysisDTO
    func triggerSync(authorID: Int) async throws
}

final class APIClient: APIClientProtocol {
    private let baseURLProvider: BaseURLProviding
    private let decoder: JSONDecoder

    init(baseURLProvider: BaseURLProviding) {
        self.baseURLProvider = baseURLProvider
        self.decoder = JSONDecoder()
        self.decoder.keyDecodingStrategy = .convertFromSnakeCase
        self.decoder.dateDecodingStrategy = .iso8601
    }

    func fetchDashboard(authorID: Int) async throws -> DashboardDTO {
        try await get(path: "/dashboard", query: [URLQueryItem(name: "author_id", value: "\(authorID)")])
    }

    func fetchPapers(authorID: Int) async throws -> [PaperSummaryDTO] {
        try await get(path: "/papers", query: [URLQueryItem(name: "author_id", value: "\(authorID)")])
    }

    func fetchMetrics(authorID: Int) async throws -> MetricsDTO {
        try await get(path: "/metrics", query: [URLQueryItem(name: "author_id", value: "\(authorID)")])
    }

    func fetchHIndex(authorID: Int) async throws -> HIndexAnalysisDTO {
        try await get(path: "/metrics/hindex-analysis", query: [URLQueryItem(name: "author_id", value: "\(authorID)")])
    }

    func triggerSync(authorID: Int) async throws {
        var req = try URLRequest(url: url(path: "/sync"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["author_id": authorID])
        _ = try await URLSession.shared.data(for: req)
    }

    private func get<T: Decodable>(path: String, query: [URLQueryItem]) async throws -> T {
        let endpoint = try url(path: path, query: query)
        let (data, response) = try await URLSession.shared.data(from: endpoint)
        guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }
        return try decoder.decode(T.self, from: data)
    }

    private func url(path: String, query: [URLQueryItem] = []) throws -> URL {
        guard var components = URLComponents(url: baseURLProvider.baseURL, resolvingAgainstBaseURL: false) else {
            throw URLError(.badURL)
        }
        components.path = path
        components.queryItems = query
        guard let url = components.url else { throw URLError(.badURL) }
        return url
    }
}
