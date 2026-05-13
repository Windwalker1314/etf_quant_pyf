# ETFQuantApp

Native SwiftUI iOS prototype for the ETF Quant product direction.

This is a local prototype, not an App Store ready financial product. Investment apps usually require stronger compliance, licensing, review evidence, privacy disclosures, and platform-specific financial content handling. Treat this project as a product research artifact and native UI playground.

## Run

Open `ETFQuantApp.xcodeproj` in Xcode, select an iPhone simulator, and run the `ETFQuantApp` target.

This repository currently has only Apple Command Line Tools active, so `xcodebuild` cannot compile the iOS target until full Xcode is selected with `xcode-select`.

## Demo Features

- Strategy marketplace and subscription state.
- Beginner profile with capital and risk preference.
- Recommended strategy logic.
- Daily rebalance reminder scheduling with local notifications.
- Backtest curve using Swift Charts.
- Rebalance order preview and target allocation.
- Trust score, verification records, creator profile, and risk disclosure.
- Creator studio concept for publishing strategies and platform revenue share.
- Embedded sample data with a clear repository boundary for future API integration.

## Local Preview First

Because the current Mac does not have a compatible full Xcode installation, use the browser prototype as the main local iteration surface:

```bash
python3 -m http.server 8877 --directory ../../demos/ios-mobile
```

Then open <http://127.0.0.1:8877>.
