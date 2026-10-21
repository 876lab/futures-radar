#!/usr/bin/env python3
"""One-off check: does the SEC accept us with its exact sample headers? Prints status codes only."""
import urllib.request
UA = "Futures Radar 876lab@users.noreply.github.com"
for host, u in [("www.sec.gov", "https://www.sec.gov/news/pressreleases.rss"), ("www.sec.gov", "https://www.sec.gov/files/company_tickers.json"),
                ("data.sec.gov", "https://data.sec.gov/submissions/CIK0000320193.json")]:
    for hdrs in ({"User-Agent": UA, "Accept-Encoding": "gzip, deflate", "Host": host},
                 {"User-Agent": UA, "Accept-Encoding": "gzip, deflate", "Host": host, "Accept": "application/json,text/xml,*/*", "From": "876lab@users.noreply.github.com"}):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=hdrs), timeout=30) as r:
                print(r.status, u, len(hdrs))
        except urllib.error.HTTPError as e:
            body = e.read()[:300]
            print(e.code, u, len(hdrs), body[:200])
        except Exception as e:
            print("ERR", u, e)
