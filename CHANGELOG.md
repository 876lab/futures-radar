# Changelog

Newest first. Plain-language summaries also go into `changes.json`, which the app shows under **What's new**.

## 2026-10-21
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
