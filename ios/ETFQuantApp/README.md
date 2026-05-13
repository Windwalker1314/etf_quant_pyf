# ETFQuantApp

Native SwiftUI iOS demo for the ETF Quant product direction.

## Run

Open `ETFQuantApp.xcodeproj` in Xcode, select an iPhone simulator, and run the `ETFQuantApp` target.

This repository currently has only Apple Command Line Tools active, so `xcodebuild` cannot compile the iOS target until full Xcode is selected with `xcode-select`.

## Demo Features

- Strategy selection.
- Daily rebalance reminder scheduling with local notifications.
- Backtest curve using Swift Charts.
- Rebalance order preview.
- Embedded sample data with a clear repository boundary for future API integration.
