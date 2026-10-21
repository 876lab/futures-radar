#!/usr/bin/env python3
"""One-off check: print the SEC's refusal page text, to learn why it refuses GitHub's servers."""
import gzip, re, urllib.request
UA = "Futures Radar 876lab@users.noreply.github.com"
try:
    urllib.request.urlopen(urllib.request.Request("https://data.sec.gov/submissions/CIK0000320193.json",
        headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate", "Host": "data.sec.gov"}), timeout=30)
    print("accepted")
except urllib.error.HTTPError as e:
    b = e.read()
    try: b = gzip.decompress(b)
    except Exception: pass
    t = re.sub(r"<[^>]+>", " ", b.decode("utf-8", "replace"))
    print(e.code, " ".join(t.split())[:1500])
