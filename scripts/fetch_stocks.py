#!/usr/bin/env python3
"""Builds stocks.json for the Quality Picks page of Futures Radar.

Runs once a day on GitHub Actions. Uses only the standard library and free, key-less sources:
  - SEC EDGAR XBRL "frames" API (https://www.sec.gov/search-filings/edgar-application-programming-interfaces):
    one call returns one number (e.g. net income for 2024) for every US-listed company.
  - SEC company_tickers.json to map tickers to SEC company numbers (CIK).
  - Wikipedia's "List of S&P 500 companies" table for the S&P 500 members.
  - The STOCKS list in index.html for the stocks that have futures on Gate, Binance or Coinbase.
The SEC asks for no more than 10 requests per second and a User-Agent with a contact; we stay far below that.
Every source is optional; failures are recorded in the output instead of stopping the run.
Prices are NOT fetched here: the app adds live prices from the exchanges for stocks it can trade.
"""
import datetime as dt
import gzip
import html.parser
import json
import re
import sys
import time
import urllib.request

UA = "FuturesRadar/1.0 (+https://github.com/876lab/futures-radar; 876lab@users.noreply.github.com)"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
FRAMES = "https://data.sec.gov/api/xbrl/frames/{tax}/{tag}/{unit}/{period}.json"
SP500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
errors = []


def get(url, tries=3):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body.decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # frame not published (yet)
            if k == tries - 1:
                raise
        except Exception:
            if k == tries - 1:
                raise
        time.sleep(2 + 3 * k)


def norm(t):
    return t.strip().upper().replace(".", "-")


class TableParser(html.parser.HTMLParser):
    """Rows of the table with id="constituents" as lists of cell text."""
    def __init__(self):
        super().__init__(); self.depth = 0; self.rows = []; self.cell = None; self.row = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            if self.depth or a.get("id") == "constituents":
                self.depth += 1
        elif self.depth == 1 and tag == "tr":
            self.row = []
        elif self.depth == 1 and tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag == "table" and self.depth:
            self.depth -= 1
        elif self.depth == 1 and tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split())); self.cell = None
        elif self.depth == 1 and tag == "tr" and self.row is not None:
            if self.row: self.rows.append(self.row)
            self.row = None

    def handle_data(self, d):
        if self.cell is not None:
            self.cell.append(d)


def sp500():
    p = TableParser(); p.feed(get(SP500))
    head = [h.lower() for h in p.rows[0]]
    si, ni = head.index("symbol"), head.index("security")
    ci = head.index("cik") if "cik" in head else None
    out = {}
    for r in p.rows[1:]:
        if len(r) > max(si, ni):
            out[norm(r[si])] = {"name": r[ni], "cik": int(r[ci]) if ci is not None and r[ci].isdigit() else None}
    if len(out) < 400:
        raise RuntimeError(f"only {len(out)} rows parsed")
    return out


def tradeable(path):
    src = open(path, encoding="utf-8").read()
    m = re.search(r"const STOCKS=new Set\('([^']+)'", src)
    return set(m.group(1).split()) if m else set()


def frame(tax, tag, unit, period):
    """{cik: value} for one concept and period; {} if the frame doesn't exist."""
    time.sleep(0.25)  # ~4 requests per second, well under the SEC's limit of 10
    try:
        body = get(FRAMES.format(tax=tax, tag=tag, unit=unit, period=period))
    except Exception as e:
        errors.append(f"{tag} {period}: {e}"); return {}
    if not body:
        return {}
    return {d["cik"]: d["val"] for d in json.loads(body).get("data", [])}


def first(*maps):
    """Merge maps, earlier ones win (fallback tags)."""
    out = {}
    for m in reversed(maps):
        out.update(m)
    return out


def main(out_path, app_path):
    now = dt.datetime.now(dt.timezone.utc)
    years = list(range(now.year - 6, now.year + 1))  # e.g. 2020..2026; latest 5 with data are used
    try:
        sec = json.loads(get(SEC_TICKERS))
        by_ticker = {norm(v["ticker"]): (int(v["cik_str"]), v["title"]) for v in sec.values()}
    except Exception as e:
        errors.append(f"SEC tickers: {e}"); by_ticker = {}
    try:
        sp = sp500()
    except Exception as e:
        errors.append(f"S&P 500 list: {e}"); sp = {}
    trade = tradeable(app_path)

    universe = {}
    for t, v in sp.items():
        cik = v["cik"] or (by_ticker.get(t) or (None,))[0]
        if cik: universe[t] = {"t": t, "name": v["name"], "cik": cik, "sp": True}
    for t in sorted(trade):
        if t in universe:
            universe[t]["trade"] = True
        elif t in by_ticker:
            cik, title = by_ticker[t]
            universe[t] = {"t": t, "name": title.title(), "cik": cik, "sp": False, "trade": True}
        else:
            universe[t] = {"t": t, "name": "", "cik": None, "sp": False, "trade": True}

    G, USD = "us-gaap", "USD"
    ni, eps, ocf, capex = {}, {}, {}, {}
    for y in years:
        p = f"CY{y}"
        ni[y] = first(frame(G, "NetIncomeLoss", USD, p), frame(G, "ProfitLoss", USD, p))
        eps[y] = first(frame(G, "EarningsPerShareDiluted", "USD-per-shares", p), frame(G, "EarningsPerShareBasic", "USD-per-shares", p))
        ocf[y] = frame(G, "NetCashProvidedByUsedInOperatingActivities", USD, p)
        capex[y] = frame(G, "PaymentsToAcquirePropertyPlantAndEquipment", USD, p)
    # balance sheet at each year end, plus the latest quarter
    eq, quarters = {}, [f"CY{y}Q4I" for y in years[:-1]] + [f"CY{years[-1]}Q{q}I" for q in (1, 2, 3)]
    for q in quarters:
        eq[q] = first(frame(G, "StockholdersEquity", USD, q), frame(G, "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", USD, q))
    debt = {}
    for q in quarters[-4:]:
        lt = frame(G, "LongTermDebt", USD, q)
        nc, cur = frame(G, "LongTermDebtNoncurrent", USD, q), frame(G, "LongTermDebtCurrent", USD, q)
        cl = frame(G, "LongTermDebtAndCapitalLeaseObligations", USD, q)
        d = {}
        for cik in set(lt) | set(nc) | set(cl):
            d[cik] = max(lt.get(cik, 0), nc.get(cik, 0) + cur.get(cik, 0), cl.get(cik, 0))
        debt[q] = d

    for s in universe.values():
        c = s["cik"]
        if not c:
            s["note"] = "no SEC filings"; continue
        ys = [y for y in years if c in ni[y]][-5:]
        if len(ys) < 3:
            s["note"] = "not enough US filings (foreign companies file differently)"; continue
        s["years"] = ys
        s["ni"] = [round(ni[y][c]) for y in ys]
        s["eps"] = [round(eps[y][c], 4) if c in eps[y] else None for y in ys]
        s["fcf"] = [round(ocf[y][c] - capex[y].get(c, 0)) if c in ocf[y] else None for y in ys]
        last = ys[-1]
        e1, e0 = eq.get(f"CY{last}Q4I", {}).get(c), eq.get(f"CY{last-1}Q4I", {}).get(c)
        if e1 is None:  # fiscal year not on the calendar: use the latest balance we have
            e1 = next((eq[q][c] for q in reversed(quarters) if c in eq[q]), None)
        rnd = lambda v: None if v is None else round(v)
        s["equity"], s["equityPrev"] = rnd(e1), rnd(e0)
        s["debt"] = rnd(next((debt[q][c] for q in reversed(quarters[-4:]) if c in debt[q]), None))

    out = {"updated": int(now.timestamp()), "source": "SEC EDGAR XBRL frames; S&P 500 list from Wikipedia",
           "stocks": sorted(universe.values(), key=lambda s: s["t"]), "errors": errors}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    ok = sum(1 for s in universe.values() if "years" in s)
    print(f"{len(universe)} stocks, {ok} with data, {len(errors)} errors")
    for e in errors[:20]:
        print("  -", e)
    if ok < 50:
        sys.exit("too little data; not publishing")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "index.html")
