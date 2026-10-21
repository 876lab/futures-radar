# Changelog

Newest first. Plain-language summaries also go into `changes.json`, which the app shows under **What's new**.

## 2026-10-21 (owner request: undo always-visible bottom bar)
- The chart screen covers the bottom bar again on phones, as before. The Settings page and its bar button stay.

## 2026-10-21 (owner request: bottom bar and Settings)
- The bottom bar now stays on screen everywhere on a phone, including the chart screen (it sits above the chart; the chart screen stops at the bar). Tapping a bar button from a chart closes the chart and opens that page.
- **Settings** is now a full page and the sixth button on the bottom bar (the top-right sliders button opens the same page). Sections: **Look** (theme; roomy/compact rows), **Trading** (candle size for signals and Setups; account size and risk % used by Size this trade; max loss per trade), **Warnings** (big news warning on/off, on by default), **Data** (feed status; relay address with its own save-and-reload button), **App health**, **Help**. Changes save on the device as you type; only the relay reloads prices.
- What's new dot now also lights up for a second update on the same day.
- Browser test now opens Settings in both themes, checks the bottom bar is on top of the chart screen, and taps it from a chart.

## 2026-10-21 (nightly run)
- **Economic event guard.** When a high-impact US event from the News calendar (`calendar` in `news.json`, e.g. CPI, jobs, FOMC) is within 30 minutes before or after now, an amber note appears at the top of the signal card and the Setups page: time of the release in his local time, minutes until/since, and "consider waiting until about …" (release + 30 min). Events at the same minute are grouped. Information only; Enter/Hold/Avoid and entry/stop/target maths are unchanged. Only USD high-impact events count (crypto is priced in dollars; e.g. UK or NZ CPI don't trigger it).
- The app now also fetches the news file while on Setups (it already did on the chart screen) and re-checks the warning every 20 seconds. Help has a "Big news warning" entry.
- New pure function `eventGuard` with 6 tests in `tests/engine.js`; the browser test now feeds a CPI release 15 minutes out and checks the warning shows on Setups and the signal card in both themes.
- Sources: NexusFi, news event risk management (https://nexusfi.com/a/risk-management/news-event-risk-management); Volmex, "Macroeconomic Announcements Fuel Volatility" (https://volmex.finance/Macroeconomic%20Announcements%20Fuel%20Volatility%20An%20In-Depth%20Analysis.pdf); "Monetary Policy, Digital Assets, and DeFi Activity" (https://arxiv.org/pdf/2302.10252). Calendar data: the existing Forex Factory weekly feed read by `scripts/fetch_news.py` (no new endpoints).

## 2026-10-21
- Safety nets (owner request: keep one bug from breaking the app). (1) `tests.yml`: the full test suite now also runs on GitHub for every push, with screenshots kept on failure. (2) `health.yml` + `tests/health.py`: a daily check of the live site at 5:23am Jamaica time (page loads, every page renders, a market chart opens, news is fresh, Gate answers, no JavaScript errors, nothing in the app's health log); GitHub emails the owner only on failure. (3) In the app, each page and the chart screen are isolated: a failure shows "This page hit a snag" with Try again, the rest keeps working, and the error is saved under Settings → App health with a Copy details button. Browser tests now block exchange addresses so results don't depend on the network, and include a deliberate breakage test.
- Replaced Coinbase with **Bybit** (owner request: Coinbase was blocked for him). Market list from `/v5/market/instruments-info` + `/v5/market/tickers` (USDT-settled perpetuals and futures), candles from `/v5/market/kline` (real 4H candles now, no 6H stand-in), live prices from the public WebSocket `tickers.*` topic (80 busiest + starred markets) and live chart candles from `kline.*`. Also handles Bybit's `SHIB1000`-style names. Coinbase's CME-style gold/oil futures are gone; gold and other TradFi markets still come from Binance and Gate.
- Sources: Bybit V5 docs: integration guide (https://bybit-exchange.github.io/docs/v5/guide), tickers (https://bybit-exchange.github.io/docs/v5/market/tickers), instruments (https://bybit-exchange.github.io/docs/v5/market/instrument), kline (https://bybit-exchange.github.io/docs/v5/market/kline), WebSocket connect (https://bybit-exchange.github.io/docs/v5/ws/connect). Browser (CORS) support confirmed via the aggr project (https://github.com/Sylar963/aggr/pull/2). Bybit restricted countries (Jamaica not listed): https://www.coinperps.com/ru/learn/bybit-restricted-countries
- Owner decided to skip Picks for now: removed the Picks page, its tests, the stocks job and script. Code kept in history (commit c701ecd) for later.
- Follow-up: the SEC refuses downloads from GitHub's servers (HTTP 403), so stocks.json has not been published yet. The SEC's own refusal page confirms it flags GitHub's server network, so a different contact email would not help. The Picks page says so plainly, and the stocks job's daily schedule is paused until a data route works (see ROADMAP notes).
- New **Picks** page (bottom bar), requested by the owner. Stocks are scored on six habits shared by at least three of ten great stock pickers (Buffett, Munger, Graham, Lynch, Fisher, Templeton, Greenblatt, Klarman, Terry Smith, O'Neil): good business (ROE ≥ 15%), fair price (P/E ≤ 20 or PEG ≤ 1), low debt (≤ 3 years of profit), growing (≥ 5% a year, at most one down year), real cash (free cash flow positive 3 years) and no losing years (5 years). Two lists: stocks with futures on Gate/Binance/Coinbase (6 checks with the live price) and S&P 500 top scores (5 checks, no price). Plus a "your part" checklist and a Help entry.
- New daily job `.github/workflows/stocks.yml` + `scripts/fetch_stocks.py` publishing `stocks.json` to the `stocks-data` branch.
- New `qualityCheck` with 13 tests; browser test now walks the Picks page with a fixture.
- Sources: SEC EDGAR APIs (https://www.sec.gov/search-filings/edgar-application-programming-interfaces), SEC developer fair-access guidance (https://www.sec.gov/about/developer-resources); investor methods from Berkshire Hathaway shareholder letters, Graham's *The Intelligent Investor*, Lynch's *One Up on Wall Street*, Fisher's *Common Stocks and Uncommon Profits*, Greenblatt's *The Little Book That Beats the Market*, Klarman's *Margin of Safety*, Smith's *Investing for Growth*, O'Neil's *How to Make Money in Stocks*; summaries checked against Validea (https://www.validea.com/peter-lynch) and Hedge Fund Alpha (https://hedgefundalpha.com/strategies/the-worlds-99-greatest-investors/). Stooq was ruled out for prices because it now requires an API key (https://github.com/pydata/pandas-datareader/issues/1012).

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
