# Futures Radar roadmap

The working plan for nightly improvement runs. Each run picks the **first unchecked item** in the backlog (unless an item is marked blocked), researches it, builds it, tests it, and ticks it off here.

## About the owner and the app

- The owner is a day trader in Jamaica (UTC-5) who trades crypto futures, mostly on Gate, and reads charts with **Bollinger bands (20,2), Supertrend (10,3), RSI 6/12/24 and MACD (12,26,9)**, the same tools as the Gate app.
- He is still learning, so everything must be **plain language, mobile-first and light**. Avoid jargon or explain it in one line. No clutter.
- He asked for **no Claude connectors**. Data comes straight from exchange public APIs in the browser, or from the repo's own GitHub Actions job.
- Live app: https://876lab.github.io/futures-radar/ (GitHub Pages from `main`, file `index.html`).

## How the app is built

- One file: `index.html` (HTML, CSS, JS inline). Libraries: TradingView Lightweight Charts 4.2.0 from jsDelivr; Inter font from Google Fonts.
- Data: Binance USDⓈ-M, Gate USDT and Coinbase futures REST for lists/candles; WebSocket streams for live prices (Binance `wss://fstream.binance.com/market/...`, Gate `wss://fx-ws.gateio.ws/v4/ws/usdt`, Coinbase `wss://advanced-trade-ws.coinbase.com`).
- News: `scripts/fetch_news.py` runs every 15 min in `.github/workflows/news.yml` and force-pushes `news.json` to the `news-data` branch; the app reads it from raw.githubusercontent.com.
- Signal engine: `computeSeries` → `analyzeAt(cs,S,L)` → `recommend(an,cs,han,tf)`. Indicators only look backwards; `tests/engine.js` proves it.
- Simulator: `backtestSeries` + `simTrade` + `simStats`; entries at next candle open, stop first when both touched, fees/slippage both sides.
- `changes.json` feeds the in-app **What's new** panel (newest first).
- Section comments in the script are used by `tests/engine.js` to slice code; keep them.

## Rules for every nightly run

1. **One focused improvement per night.** Keep the diff reviewable (aim for under ~300 changed lines). Small and correct beats big.
2. **Run `bash tests/run.sh` before pushing.** Push only if it prints `ALL CHECKS PASSED`. If you cannot make it pass, revert your app changes and push only notes in this file.
3. **Do not change the signal rules** (`analyzeAt`, `recommend`, entry/stop/target maths) unless backtest evidence shows an improvement across many markets (see the backtest item below). Until then, new signal ideas ship as **information or opt-in toggles**, never silently changing Enter/Hold/Avoid.
4. **Never remove features**, never change hosting or repository settings, never delete branches, never add paid services, API keys or secrets, never add Claude connectors.
5. **Do not touch the login.** The owner is choosing the login approach with Claude on Saturday 24 October 2026.
6. Keep the look consistent: existing colour tokens, Inter, light and dark themes both working, phone width ~390px first.
7. Add tests for new logic in `tests/engine.js` where it is pure maths.
8. After building: add a dated entry to `CHANGELOG.md` (with sources used), add a short plain-language entry to the top of `changes.json` (1–4 bullets, written for the owner), tick the item here, and add any good new ideas from research to the backlog.

## Backlog (top = next)

- [ ] **Closed-candle confirmation.** The live signal can flip while a candle is still forming. Show whether the signal is *confirmed* (from the last closed candle) or *forming*, with a countdown to candle close, and default the list tags to closed candles. Simulator already uses closed candles.
- [ ] **Economic event guard.** Using `calendar` in `news.json`, warn on the signal card and Setups list when a high-impact event (CPI, FOMC, jobs) is within 30 minutes before/after: "Big news at 8:30 — spreads and spikes are common. Consider waiting."
- [ ] **Nightly backtest report (evidence for rule changes).** Add a GitHub Actions job that downloads recent candles for the top markets (Gate and Coinbase first; Binance may block US servers, so record failures), runs the same engine in Node, and publishes `backtest.json` to a `backtest-data` branch. Show "Last night's results" in the Simulator. Use it to judge any rule change.
- [ ] **VWAP.** Daily (UTC) VWAP line on the chart and a check on the signal card ("Price above today's VWAP"). Day traders use it as the fair-value line. Information only at first.
- [ ] **Multi-timeframe strip.** On the chart screen, a row showing the signal on 5m / 15m / 1H / 4H at once, so agreement is visible at a glance.
- [ ] **Open interest and funding context.** From exchange public APIs (e.g. Binance `openInterest` and `openInterestHist`, Gate contract stats): OI change over 24h and a "crowded" warning when funding is extreme. Explain in one line.
- [ ] **RSI divergence.** Detect regular bullish/bearish divergence between price swings and RSI 12; mark it on the chart and mention it on the signal card (information only).
- [ ] **Support and resistance from swing points.** Draw the nearest 2–3 swing highs/lows as levels; use them in the "Recent low/high" display.
- [ ] **Trade journal.** Log trades (market, side, entry, stop, exit, size) on the device; show win rate and average R; compare with what the signal said. Export as CSV via the page (downloads only where allowed).
- [ ] **Unusual activity scanner.** A section (inside Hot) for volume spikes vs the 20-candle average and sudden moves in the last hour.
- [ ] **Trading sessions and liquidity.** Show the current session (Asia / London / New York) and warn in thin hours and weekends.
- [ ] **Price and signal alerts while the app is open.** Starred markets: sound/vibration and an in-app notice when a signal turns to Enter long/short or price crosses a level.
- [ ] **Coinbase international perpetuals live.** Stream INTX perps (separate host) so they update every second.
- [ ] **Performance and accessibility pass.** Check with 1,300+ markets, keyboard use, contrast in both themes.

## Done

- [x] Merged markets across Binance, Gate and Coinbase; categories; Hot tab
- [x] Enter / Hold / Avoid signal with entry zone, stop, targets, confidence; Gate-style chart with B/S marks
- [x] Live WebSocket prices and candles
- [x] Simulator with stress test
- [x] Inter font; bottom tab bar; compact rows; sparklines; swipe/back; sticky search; light/dark switch
- [x] News page (headlines, Fear & Greed, calendar, X links) and per-market headlines
- [x] Automated test suite (`tests/run.sh`) and What's new panel

## Notes from runs

(Each run adds a dated line here if something was blocked or needs the owner.)
