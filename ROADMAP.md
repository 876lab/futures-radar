# Futures Radar roadmap

The working plan for nightly improvement runs. Each run picks the **first unchecked item** in the backlog (unless an item is marked blocked), researches it, builds it, tests it, and ticks it off here.

## About the owner and the app

- The owner is a day trader in Jamaica (UTC-5) who trades crypto futures, mostly on Gate, and reads charts with **Bollinger bands (20,2), Supertrend (10,3), RSI 6/12/24 and MACD (12,26,9)**, the same tools as the Gate app.
- He is still learning, so everything must be **plain language, mobile-first and light**. Avoid jargon or explain it in one line. No clutter.
- From his Gate stats (shared 19 Oct 2026): ~3–4 positions a day; winners held ~6–9 hours, losers ~4 hours; win rate ~52–53%. Last 30 days: +602 USDT, reward-to-risk 1.5:1. Over 180 days: +137 USDT, 0.94:1, with one −1,038 USDT loss that erased most gains. Shorts have clearly done better than longs recently. He **does not trade off candle closes**, so candle-close timing is low priority. What matters most to him: avoiding outsized losses, picking direction (long vs short) well, and multi-hour holds (1H/4H context).
- He asked for **no Claude connectors**. Data comes straight from exchange public APIs in the browser, or from the repo's own GitHub Actions job.
- Live app: https://876lab.github.io/futures-radar/ (GitHub Pages from `main`, file `index.html`).

## How the app is built

- One file: `index.html` (HTML, CSS, JS inline). Libraries: TradingView Lightweight Charts 4.2.0 from jsDelivr; Inter font from Google Fonts.
- Data: Binance USDⓈ-M, Gate USDT and Bybit V5 linear (USDT perpetuals and futures) REST for lists/candles; WebSocket streams for live prices (Binance `wss://fstream.binance.com/market/...`, Gate `wss://fx-ws.gateio.ws/v4/ws/usdt`, Bybit `wss://stream.bybit.com/v5/public/linear`, the 80 busiest Bybit markets plus starred ones). Coinbase was replaced by Bybit on 2026-10-21 at the owner's request (Coinbase was blocked for him). Bybit blocks US IPs, so it can't be tested from GitHub's US servers.
- News: `scripts/fetch_news.py` runs every 15 min in `.github/workflows/news.yml` and force-pushes `news.json` to the `news-data` branch; the app reads it from raw.githubusercontent.com.
- Signal engine: `computeSeries` → `analyzeAt(cs,S,L)` → `recommend(an,cs,han,tf)`. Indicators only look backwards; `tests/engine.js` proves it.
- Simulator: `backtestSeries` + `simTrade` + `simStats`; entries at next candle open, stop first when both touched, fees/slippage both sides.
- (Parked) Stocks: `scripts/fetch_stocks.py` ran daily in `.github/workflows/stocks.yml` and force-pushes `stocks.json` (yearly company numbers from the SEC XBRL frames API for the S&P 500 and the stock futures in `STOCKS`) to the `stocks-data` branch. The **Picks** page scores them with `qualityCheck` (6 checks; fair price only when a live futures price exists). SEC contact in the User-Agent is the GitHub noreply address, chosen by the owner.
- Safety nets: `.github/workflows/tests.yml` re-runs `tests/run.sh` on GitHub for every push to main; `.github/workflows/health.yml` runs `tests/health.py` daily against the live site (Binance/Bybit can't be reached from GitHub's US servers and are only noted). In the app, `renderList` and the chart screen catch errors and show a "hit a snag" card; errors are logged on the device (Settings → App health) for the owner to copy to Claude.
- `changes.json` feeds the in-app **What's new** panel (newest first).
- Section comments in the script are used by `tests/engine.js` to slice code; keep them.

## Rules for every nightly run

1. **One focused improvement per night.** Keep the diff reviewable (aim for under ~300 changed lines). Small and correct beats big.
2. **Run `bash tests/run.sh` before pushing.** Push only if it prints `ALL CHECKS PASSED`. After pushing, check that the GitHub **Tests** run is green; if the **Daily health check** is red, fixing it comes before any backlog item. If you cannot make it pass, revert your app changes and push only notes in this file.
3. **Do not change the signal rules** (`analyzeAt`, `recommend`, entry/stop/target maths) unless backtest evidence shows an improvement across many markets (see the backtest item below). Until then, new signal ideas ship as **information or opt-in toggles**, never silently changing Enter/Hold/Avoid.
4. **Never remove features**, never change hosting or repository settings, never delete branches, never add paid services, API keys or secrets, never add Claude connectors.
5. **Do not touch the login.** The owner is choosing the login approach with Claude on Saturday 24 October 2026.
6. Keep the look consistent: existing colour tokens, Inter, light and dark themes both working, phone width ~390px first.
7. Add tests for new logic in `tests/engine.js` where it is pure maths.
8. After building: add a dated entry to `CHANGELOG.md` (with sources used), add a short plain-language entry to the top of `changes.json` (1–4 bullets, written for the owner), tick the item here, and add any good new ideas from research to the backlog.

## Backlog (top = next)

- [x] **Max-loss guard.** (done 2026-10-20) In Settings, let him set a maximum loss per trade in USDT (suggest twice his average loss). The **Size this trade** calculator and signal card then warn in red when a planned trade would lose more than that at the stop, and suggest the smaller size that fits. One oversized loss (−1,038 USDT) wiped out months of gains; this is the most valuable protection.
- [x] **Economic event guard.** (done 2026-10-21; high-impact USD events only) Using `calendar` in `news.json`, warn on the signal card and Setups list when a high-impact event (CPI, FOMC, jobs) is within 30 minutes before/after: "Big news at 8:30 — spreads and spikes are common. Consider waiting."
- [x] **Event guard follow-ups (small).** (done 2026-10-22; JPY, CNY and EUR as the extra countries) (a) Optional setting to also count other big releases (e.g. Bank of Japan, China data) that sometimes move crypto; (b) a quiet "big news today at …" line on Setups earlier in the day, so he can plan around it instead of only seeing it 30 minutes before.
- [ ] **Import my trades.** In the Simulator, let him load his Gate position-history export (CSV or Excel saved as CSV). Parse open/close time, contract, side, size, entry/exit price, realized PnL and fees. Show his stats by coin, long vs short, hour of day, weekday and holding time, and, using exchange candles fetched in the browser, what the app's signal said on 1H and 4H at each entry. Everything stays on his device. Keep the parser tolerant of column-name differences.
- [ ] **Win-odds research, step 1: nightly backtest report (evidence for rule changes).** Add a GitHub Actions job that downloads recent candles for the top markets (Gate first; Binance and Bybit block US servers, so record failures), runs the same engine in Node, and publishes `backtest.json` to a `backtest-data` branch. **Record the conditions at every simulated entry** (timeframe, confidence, ADX, volume ratio, RSI 6, distance from EMA20 in ATRs, Bollinger %B, bigger-timeframe agreement, 4H/1D direction, ATR percentile vs recent weeks, funding where available, UTC hour/session, weekday) and its result (target / stop / time exit, R). Show "Last night's results" in the Simulator. Use it to judge any rule change.
- [ ] **Win-odds research, step 2: win-rate tables.** In the Simulator, show win rate to target 1 and average R by condition bucket (confidence band, ADX band, volume, trend agreement, volatility regime, session, weekday, long vs short). Show trade counts and a range (Wilson interval); hide buckets with too few trades (e.g. under 100).
- [ ] **Win-odds research, step 3: win odds on the signal card (information only).** E.g. "Setups like this reached target 1 in 58% of 1,240 past trades (range 55–61%)." Start with bucket look-ups; later a simple meta-labeling model (logistic regression trained in the GitHub job on older data, judged on newer data, weights published in `backtest.json`). Never changes Enter/Hold/Avoid.
- [ ] **Win-odds research, step 4: opt-in "Only show high-odds setups" switch on Setups.** Only after walk-forward (newer, unseen data) results show a real edge across many markets; check probability of backtest overfitting / deflated Sharpe before shipping. Off by default.
- [ ] **Long vs short bias panel.** On the chart screen, a one-line read of which side the bigger picture (4H and 1D) favours, since picking the side well matters more to him than exact entry timing.
- [ ] **Multi-timeframe strip.** On the chart screen, a row showing the signal on 15m / 1H / 4H / 1D at once, so agreement is visible at a glance.
- [ ] **VWAP.** Daily (UTC) VWAP line on the chart and a check on the signal card ("Price above today's VWAP"). Information only at first.
- [ ] **Open interest and funding context.** From exchange public APIs (e.g. Binance `openInterest` and `openInterestHist`, Gate contract stats): OI change over 24h and a "crowded" warning when funding is extreme. Explain in one line.
- [ ] **RSI divergence.** Detect regular bullish/bearish divergence between price swings and RSI 12; mark it on the chart and mention it on the signal card (information only).
- [ ] **Support and resistance from swing points.** Draw the nearest 2–3 swing highs/lows as levels; use them in the "Recent low/high" display.
- [ ] **Trade journal.** Log trades on the device; show win rate and average R; compare with what the signal said. Builds on "Import my trades".
- [ ] **Daily loss limit.** Builds on the journal/import: a Settings cap for one day's total losses; once reached, the signal card says "You've hit today's loss limit — consider stopping for the day." Information only.
- [ ] **Fees in the sizing box.** Let him enter his Gate taker fee (default 0.05%) so "If stopped out" and the max-loss check include fees both ways.
- [ ] **Unusual activity scanner.** A section (inside Hot) for volume spikes vs the 20-candle average and sudden moves in the last hour.
- [ ] **Trading sessions and liquidity.** Show the current session (Asia / London / New York) and warn in thin hours and weekends.
- [ ] **Price and signal alerts while the app is open.** Starred markets: sound/vibration and an in-app notice when a signal turns to Enter long/short or price crosses a level.
- [ ] **Push notifications (parked by the owner, 22 Oct 2026; do not pick up unless he asks).** He uses an iPhone. Plan discussed: (1) make the app a proper Home Screen app (icon + manifest); (2) in-app alerts while open (iPhone Safari can't vibrate); (3) background Web Push from a GitHub job checking Gate every 5–15 min. Step 3 needs his OK for a signing key as a GitHub secret, the app added to the Home Screen (iOS 16.4+), and a way for the job to know his starred markets (depends on the login decision). Free alternative: the ntfy app.
- [ ] **Picks (parked by the owner, 21 Oct 2026; do not pick up unless he asks).** Stocks scored on 6 traits shared by great investors. Built and then removed because the SEC blocks GitHub's servers; full code is in commit c701ecd (plus fixes up to d96b7ae). Revive only with a working data route (e.g. download run on the owner's computer).
- [ ] **Big news on the News calendar by country.** Small: let the News page "Coming up" card follow the same country switch, and add a one-tap "Remind me" that pins the next big release time at the top of Setups.
- [ ] **Signal forming vs confirmed (low priority).** Information only: show whether the current candle is still forming. He doesn't trade by candle closes, so keep it subtle.
- [ ] **Performance and accessibility pass.** Check with 1,300+ markets, keyboard use, contrast in both themes.

## Done

- [x] Merged markets across Binance, Gate and Coinbase; categories; Hot tab
- [x] Enter / Hold / Avoid signal with entry zone, stop, targets, confidence; Gate-style chart with B/S marks
- [x] Live WebSocket prices and candles
- [x] Simulator with stress test
- [x] Inter font; bottom tab bar; compact rows; sparklines; swipe/back; sticky search; light/dark switch
- [x] News page (headlines, Fear & Greed, calendar, X links) and per-market headlines
- [x] Automated test suite (`tests/run.sh`) and What's new panel
- [x] Safety nets: tests on GitHub, daily live health check, broken sections isolated with an App health log (2026-10-21)

## Notes from runs

(Each run adds a dated line here if something was blocked or needs the owner.)

- 2026-10-22: Owner approved the 4-step **win-odds research** plan (backtest with recorded conditions → win-rate tables → win odds on the signal card → opt-in high-odds filter). Goal: more wins at the same 1.5:1 / 3:1 targets, not a higher win rate from smaller targets. Sources: Bitcoin intraday time-series momentum (https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/); López de Prado meta-labeling / triple-barrier (https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy/); Bailey et al., Probability of Backtest Overfitting (https://papers.ssrn.com/abstract=2326253) and Deflated Sharpe Ratio (https://papers.ssrn.com/abstract=2460551); perpetual futures funding (https://arxiv.org/html/2212.06888v5).

- 2026-10-21: **Picks data blocked.** The SEC refuses every data request from GitHub Actions (data.sec.gov, sec.gov/files, Archives). Its refusal page says the request "has been identified as part of a network of automated tools outside of the acceptable policy", i.e. GitHub's server network is flagged, so changing the contact email would not help (8 runs tested). Wikidata answers but holds equity figures for only ~30 US-listed companies, too thin. Unofficial price/fundamental endpoints (Nasdaq, Yahoo) are ruled out by the "official docs" rule. Owner chose to skip the add-on for now; Picks page, stocks job and script were removed the same day.

- 2026-10-19: Owner will upload his Gate trade history; its analysis happens in chat with Claude. Priorities were reordered around his stats (max-loss guard first; candle-close item moved to the bottom).
