import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var settings: AppSettings
    @State private var notificationsEnabled = true

    var body: some View {
        Form {
            Section("Backend") {
                TextField("Base URL", text: $settings.baseURLString)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                Stepper("Author ID: \(settings.authorID)", value: $settings.authorID, in: 1...9999)
            }

            Section("Notifications") {
                Toggle("Enable milestone alerts", isOn: $notificationsEnabled)
                Text("Push scaffolding is wired in backend event feed.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("Settings")
    }
}
