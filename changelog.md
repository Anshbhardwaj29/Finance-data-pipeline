# Trading Pipeline Project Changelog & Documentation

This document logs every system modification, feature addition, and configuration change made to the `trading_pipeline` project, with timestamps, files altered, and descriptions.

---

## [2026-05-25 18:05:43] - Binance WebSocket Integration (Staging Phase)

### Added
- Created `BinanceAdapter` in `core/broker.py` to connect asynchronously to `wss://stream.binance.com:9443/ws/` for real-time unauthenticated market feeds.
- Integrated `BinanceAdapter` initialization in `main.py`.

### Modified
- Added `websockets` dependency to `requirements.txt`.
- Set active broker adapter to `binance` and defined crypto streams (`BTCUSDT`, `ETHUSDT`, etc.) in `config.yaml`.

---

## [2026-05-25 18:42:04] - Indian Stock Market Support & Analytics Upgrades

### Added
- Created `strategies/high_probability_nifty.py` containing the `HighProbabilityNiftyStrategy` (EMA 9/21 Trend Filter + RSI Momentum Confirmation + ATR Volatility Bands).
- Created `core/excel_logger.py` containing the `ExcelLogger` class to generate daily formatted excel ledgers (`logs/trading_report_YYYY-MM-DD.xlsx`) styled with Navy Segoe UI headers and conditional green/red profit/loss fills.
- Created `core/notifier.py` with `Notifier` to push trade transactions to Twilio SMS, Twilio WhatsApp, or Telegram Bot channels.
- Created `core/dashboard.py` hosting a background HTTP server on port `8050` with a glassmorphic dashboard containing portfolio widgets, live position exposure lists, audit trails, and cumulative equity curve graphs (Chart.js).

### Modified
- Installed `openpyxl` and `requests` packages and added them to `requirements.txt`.
- Modified `core/broker.py` (`PaperBroker`) to support `NIFTY50` (~22,500.00) and `BANKNIFTY` (~48,000.00) and upgraded the fluctuation drift to be price-proportional (up to 0.02% per tick).
- Integrated logging, alerts, and dashboard server into `core/engine.py`.
- Modified `main.py` to support dynamic loading of the high-probability Nifty strategy.

---

## [2026-05-25 19:06:30] - UTF-8 Terminal Handles & WhatsApp Activation

### Modified
- Modified `core/logger.py` to force standard console output (`sys.stdout`/`sys.stderr`) to write in UTF-8 format, preventing console unicode/emoji rendering warnings on Windows.
- Enabled live notifications in `config.yaml` (`enabled: true`) and loaded user's Twilio WhatsApp Sandbox credentials (`account_sid`, `auth_token`, numbers), completing verified end-to-end alert delivery.

---

## [2026-06-01 17:15:00] - ATM Index Option Simulation & Parallel RR Matrix Optimizer

### Added
- Integrated ATM option pricing model (CE/PE Buy focusing on NIFTY50 nearest 50 strikes and BANKNIFTY nearest 100 strikes) using Delta=0.5.
- Implemented **Loss-Reduction Optimizer**: trails Stop Loss to entry price (Break-Even) when price moves 50% towards target.
- Added **Parallel RR Trackers** (ratios 1:2, 1:3, 1:4, and 1:5) in both unoptimized and optimized modes.
- Added Maximum Favorable Excursion (Peak Index Points Run) logging.
- Upgraded Web Dashboard to support:
  - Open Option positions (Type, Strike, Premium P&L).
  - Parallel RR performance table comparison (optimized vs unoptimized win rate and P&L).
  - KPI cards for Losses Saved and Average Peak Run.

### Modified
- Modified `core/risk_manager.py` to calculate option strikes, premiums, manage break-even trailing SL, and track parallel RR states.
- Modified `core/engine.py` to log option-specific CE/PE entries.
- Modified `core/excel_logger.py` to expand table columns to 13, adding `Instrument`, `Entry Premium`, `Exit Premium`, and `Peak Run (Pts)`.
