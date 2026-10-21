#!/usr/bin/env python3
"""One-off check: which SEC addresses answer GitHub's servers. Prints status codes only."""
import urllib.request
UAS = ["Futures Radar 876lab@users.noreply.github.com",
       "Mozilla/5.0 (compatible; FuturesRadarNews/1.0; +https://github.com/876lab/futures-radar)"]
URLS = ["https://www.sec.gov/news/pressreleases.rss",
        "https://www.sec.gov/files/company_tickers.json",
        "https://www.sec.gov/include/ticker.txt",
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-K&output=atom",
        "https://www.sec.gov/Archives/edgar/data/320193/index.json",
        "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
        "https://data.sec.gov/submissions/CIK0000320193.json",
        "https://data.sec.gov/api/xbrl/frames/us-gaap/NetIncomeLoss/USD/CY2024.json"]
for ua in UAS:
    for u in URLS:
        try:
            req = urllib.request.Request(u, method="HEAD" if u.endswith(".zip") else "GET", headers={"User-Agent": ua, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=30) as r:
                print(r.status, r.headers.get("Content-Length"), u, "|", ua[:30])
        except Exception as e:
            print("ERR", e, u, "|", ua[:30])
