#!/usr/bin/env python3
"""Builds news.json for Futures Radar: headlines, Fear & Greed, and upcoming economic events.

Runs on GitHub Actions every 15 minutes. Uses only the standard library.
Every source is optional; failures are recorded in the output instead of stopping the run.
"""
import datetime as dt
import email.utils
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (compatible; FuturesRadarNews/1.0; +https://github.com/876lab/futures-radar)"

# (name, url, topic) — topic: crypto | markets | official
FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "crypto"),
    ("Cointelegraph", "https://cointelegraph.com/rss", "crypto"),
    ("The Block", "https://www.theblock.co/rss.xml", "crypto"),
    ("Decrypt", "https://decrypt.co/feed", "crypto"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/feed", "crypto"),
    ("CNBC Markets", "https://www.cnbc.com/id/20910258/device/rss/rss.html", "markets"),
    ("CNBC Top News", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "markets"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "markets"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex", "markets"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", "official"),
    ("SEC", "https://www.sec.gov/news/pressreleases.rss", "official"),
    ("CFTC", "https://www.cftc.gov/RSS/RSSGP/rssgp.xml", "official"),
]

# ticker -> extra names; tickers match in UPPERCASE only, names match any case
COINS = {
    "BTC": ["bitcoin"], "ETH": ["ethereum", "ether"], "SOL": ["solana"], "XRP": ["ripple"], "BNB": ["binance coin"],
    "DOGE": ["dogecoin"], "ADA": ["cardano"], "AVAX": ["avalanche"], "LINK": ["chainlink"], "DOT": ["polkadot"],
    "LTC": ["litecoin"], "TRX": ["tron"], "SUI": [], "TON": ["toncoin"], "SHIB": ["shiba inu"], "PEPE": [],
    "HYPE": ["hyperliquid"], "ENA": ["ethena"], "WLD": ["worldcoin"], "NEAR": ["near protocol"], "APT": ["aptos"],
    "ARB": ["arbitrum"], "OP": ["optimism"], "TAO": ["bittensor"], "FET": [], "RENDER": [], "BCH": ["bitcoin cash"],
    "XLM": ["stellar"], "HBAR": ["hedera"], "ATOM": ["cosmos"], "UNI": ["uniswap"], "AAVE": ["aave"], "FIL": ["filecoin"],
    "INJ": ["injective"], "SEI": [], "TIA": ["celestia"], "ONDO": [], "JUP": ["jupiter"], "WIF": ["dogwifhat"],
    "BONK": [], "TRUMP": ["official trump"], "PENGU": ["pudgy penguins"], "FARTCOIN": [], "VIRTUAL": ["virtuals protocol"],
    "XAU": ["gold price", "gold prices", "gold futures", "spot gold"], "XAG": ["silver price", "silver prices", "silver futures"],
    "WTI": ["crude oil", "oil prices", "brent"], "NATGAS": ["natural gas"],
    "TSLA": ["tesla"], "NVDA": ["nvidia"], "AAPL": ["apple inc", "apple's"], "MSFT": ["microsoft"], "AMZN": ["amazon"],
    "META": ["meta platforms"], "GOOGL": ["alphabet", "google"], "COIN": ["coinbase global"], "MSTR": ["microstrategy", "strategy inc"],
    "HOOD": ["robinhood"], "CRCL": ["circle internet"],
}
# tickers that are also ordinary words or acronyms: only match by name or as $CASHTAG
WEAK = {"OP", "ARB", "LINK", "DOT", "TON", "SUI", "SEI", "UNI", "ONDO", "FET", "ENA", "COIN", "META", "TRUMP", "HYPE", "NEAR", "APT", "JUP", "WIF", "VIRTUAL", "RENDER", "ATOM"}

TAGS = [
    ("Regulation", r"\b(SEC|CFTC|regulat\w*|lawsuit|court|judge|ban(s|ned)?|senate|congress|MiCA|stablecoin law|compliance|sanction\w*)\b"),
    ("Macro", r"\b(Fed|FOMC|Powell|rate (cut|hike)s?|interest rates?|inflation|CPI|PCE|jobs report|payrolls|unemployment|GDP|tariffs?|recession|treasury yields?|bond yields?)\b"),
    ("ETF", r"\bETFs?\b"),
    ("Hack", r"\b(hack(ed|er|ers)?|exploit(ed)?|breach|stolen|drain(ed)?|heist|phishing)\b"),
    ("Listing", r"\b(lists|listing|listed|delist\w*|launch(es)? (perpetual|futures)|new trading pair)\b"),
    ("Liquidations", r"\bliquidat\w*\b"),
]


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, application/json, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def clean(s, limit=None):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    if limit and len(s) > limit:
        s = s[: limit - 1].rsplit(" ", 1)[0] + "…"
    return s


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try:
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp())


def parse_feed(data):
    """Returns [(title, link, date, summary)] for RSS or Atom; falls back to regex when XML is malformed."""
    out = []
    txt = data.decode("utf-8", "replace")
    try:
        fixed = re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", txt)
        root = ET.fromstring(fixed.encode("utf-8"))
        A = "{http://www.w3.org/2005/Atom}"
        DC = "{http://purl.org/dc/elements/1.1/}"
        for it in root.iter("item"):
            g = lambda tag: (it.findtext(tag) or "").strip()
            out.append((g("title"), g("link") or g("guid"), parse_date(g("pubDate") or g(DC + "date")), g("description")))
        for it in root.iter(A + "entry"):
            link = ""
            for l in it.findall(A + "link"):
                if l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "")
                    break
            out.append(((it.findtext(A + "title") or "").strip(), link,
                        parse_date(it.findtext(A + "published") or it.findtext(A + "updated")),
                        it.findtext(A + "summary") or it.findtext(A + "content") or ""))
        if out:
            return out
    except ET.ParseError:
        pass
    for block in re.findall(r"<item\b.*?</item>", txt, re.S | re.I):
        f = lambda tag: (re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.S | re.I) or [None, ""])[1]
        unc = lambda s: re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", s.strip(), flags=re.S)
        out.append((unc(f("title")), unc(f("link")), parse_date(unc(f("pubDate"))), unc(f("description"))))
    return out


def coins_in(text):
    found = []
    for t, names in COINS.items():
        hit = re.search(rf"\${t}\b", text) is not None
        if not hit and t not in WEAK and re.search(rf"(?<![A-Za-z$]){t}(?![A-Za-z])", text):
            hit = True
        if not hit:
            low = text.lower()
            hit = any(re.search(rf"\b{re.escape(n)}\b", low) for n in names)
        if hit:
            found.append(t)
    return found[:6]


def tags_in(text):
    return [name for name, rx in TAGS if re.search(rx, text, re.I if name not in ("Regulation", "Macro", "ETF") else 0)]


def build():
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    items, sources, seen = [], [], set()
    for name, url, topic in FEEDS:
        try:
            rows = parse_feed(fetch(url))
            n = 0
            for title, link, d, summary in rows:
                title = clean(title)
                if not title or not link:
                    continue
                key = re.sub(r"\W+", "", title.lower())[:80]
                if key in seen:
                    continue
                d = d or now
                if d > now + 3600 or now - d > 72 * 3600:
                    continue
                seen.add(key)
                body = clean(summary, 240)
                text = f"{title} {body}"
                items.append({"t": title, "u": link.strip(), "s": name, "k": topic, "d": d, "x": body,
                              "c": coins_in(text), "g": tags_in(text)})
                n += 1
            sources.append({"name": name, "ok": True, "n": n})
        except Exception as e:  # keep going; report the failure
            sources.append({"name": name, "ok": False, "err": type(e).__name__})
    items.sort(key=lambda x: -x["d"])
    items = items[:250]

    fng = None
    try:
        j = json.loads(fetch("https://api.alternative.me/fng/?limit=2"))
        d = j.get("data") or []
        if d:
            fng = {"v": int(d[0]["value"]), "l": d[0]["value_classification"], "d": int(d[0]["timestamp"]),
                   "prev": int(d[1]["value"]) if len(d) > 1 else None}
        sources.append({"name": "Fear & Greed", "ok": fng is not None})
    except Exception as e:
        sources.append({"name": "Fear & Greed", "ok": False, "err": type(e).__name__})

    cal = []
    try:
        rows = json.loads(fetch("https://nfs.faireconomy.media/ff_calendar_thisweek.json"))
        for r in rows:
            imp = r.get("impact", "")
            if not (imp == "High" or (imp == "Medium" and r.get("country") == "USD")):
                continue
            d = parse_date(r.get("date"))
            if d is None or d < now - 3 * 3600:
                continue
            cal.append({"t": r.get("title", ""), "c": r.get("country", ""), "d": d, "i": imp,
                        "f": r.get("forecast", ""), "p": r.get("previous", "")})
        cal.sort(key=lambda x: x["d"])
        sources.append({"name": "Economic calendar", "ok": True, "n": len(cal)})
    except Exception as e:
        sources.append({"name": "Economic calendar", "ok": False, "err": type(e).__name__})

    return {"v": 1, "updated": now, "items": items, "fng": fng, "calendar": cal[:30], "sources": sources}


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "news.json"
    data = build()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    ok = sum(1 for s in data["sources"] if s["ok"])
    print(f"{len(data['items'])} headlines, {ok}/{len(data['sources'])} sources ok")
    for s in data["sources"]:
        print(("  ok   " if s["ok"] else "  FAIL ") + s["name"] + (f" ({s.get('n')})" if s.get("n") is not None else "") + (f" {s.get('err')}" if s.get("err") else ""))
