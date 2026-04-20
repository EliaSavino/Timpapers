import Foundation

protocol CacheStore {
    func saveDashboard(_ dashboard: DashboardDTO)
    func loadDashboard() -> DashboardDTO?
}

final class AppCache: CacheStore {
    private let defaults: UserDefaults
    private let key = "cached_dashboard"

    init(suiteName: String = "group.com.example.timpapers") {
        self.defaults = UserDefaults(suiteName: suiteName) ?? .standard
    }

    func saveDashboard(_ dashboard: DashboardDTO) {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        if let data = try? encoder.encode(dashboard) {
            defaults.set(data, forKey: key)
        }
    }

    func loadDashboard() -> DashboardDTO? {
        guard let data = defaults.data(forKey: key) else { return nil }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .iso8601
        return try? decoder.decode(DashboardDTO.self, from: data)
    }
}

protocol BaseURLProviding {
    var baseURL: URL { get }
}

final class AppSettings: ObservableObject, BaseURLProviding {
    @Published var baseURLString: String {
        didSet { UserDefaults.standard.set(baseURLString, forKey: "backend_url") }
    }

    @Published var authorID: Int {
        didSet { UserDefaults.standard.set(authorID, forKey: "author_id") }
    }

    init() {
        self.baseURLString = UserDefaults.standard.string(forKey: "backend_url") ?? "http://127.0.0.1:8000"
        self.authorID = UserDefaults.standard.integer(forKey: "author_id") == 0 ? 1 : UserDefaults.standard.integer(forKey: "author_id")
    }

    var baseURL: URL { URL(string: baseURLString) ?? URL(string: "http://127.0.0.1:8000")! }
}
