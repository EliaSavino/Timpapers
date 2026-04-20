# TimPapers iOS App (SwiftUI + WidgetKit)

Native iPhone app source layout for tracking publications, citations, h-index, i10-index, and frontier analysis.

## Tooling
- Swift 5.10+
- SwiftUI
- Swift Charts
- WidgetKit
- URLSession + Codable networking

## Folder layout
- `App/`
- `Networking/`
- `Models/`
- `Features/` (Dashboard, Papers, PaperDetail, Metrics, Settings)
- `Persistence/Cache/`
- `WidgetExtension/`
- `Shared/`

## Setup notes
1. Create an Xcode iOS app target and Widget Extension target.
2. Set App Group in both targets (e.g., `group.com.example.timpapers`).
3. Add these sources to targets accordingly.
4. Set backend base URL in Settings.
