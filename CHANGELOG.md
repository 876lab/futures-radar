# Changelog

Newest first. Plain-language summaries also go into `changes.json`, which the app shows under **What's new**.

## 2026-10-20
- Max-loss guard: new **Max loss per trade (USDT)** setting (off by default, stored on the device). The **Size this trade** box on the signal card shows a red warning when the planned loss at the stop is above the cap, marks the box "over your max loss" even when it is closed, and suggests the size, units, leverage and risk % that fit the cap. Existing sizing maths and signal rules are unchanged.
- New pure function `sizeTrade` with 5 tests in `tests/engine.js`.
- Sources: standard fixed-risk sizing (position size = amount at risk ÷ stop distance), e.g. Plus500 "Position Sizing in Futures Trading" (https://us.plus500.com/en/newsandmarketinsights/position-sizing-guide) and NexusFi position sizing (https://nexusfi.com/a/risk-management/position-sizing-futures); Gate fee guide (https://www.gate.com/learn/articles/gate-fee-calculator-real-trading-cost) for the fees note.

## 2026-10-19
- Added the automated test suite (`tests/run.sh`): syntax, signal engine (no look-ahead, trade rules, backtest stress run) and a headless browser walk through every page in dark and light themes.
- Added the in-app What's new panel fed by `changes.json`.
- Added `ROADMAP.md` with the backlog and the rules for nightly improvement runs.

## 2026-10-17
- News page, bottom tab bar, compact rows, sparklines, swipe/back gestures, sticky search, light/dark switch.
- News job on GitHub Actions (every 15 minutes).
- Simulator tab and stress test. Inter font and denser layout.

## 2026-10-16
- First versions: merged markets, signals, Gate-style chart, live streaming, GitHub Pages hosting.
