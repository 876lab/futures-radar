"""Hourly market snapshot for the backtest research (ROADMAP: order-book depth, open interest, funding).

For the 30 busiest Gate USDT perpetuals it records, once an hour:
  order-book depth within 1% and 2% of the mid price (USDT, buy and sell side), spread,
  open interest (USDT), funding rate, long and short liquidations in the last hour (USDT), taker long/short ratio.
Rows are appended to the previous file (read from the market-data branch) and kept for 90 days, so the nightly
backtest can later test whether any of these improve the odds. Gate only: Binance and Bybit block GitHub's servers.

Sources (Gate API v4, public): /futures/usdt/tickers, /futures/usdt/contracts (quanto_multiplier),
/futures/usdt/order_book (p = price, s = size in contracts), /futures/usdt/contract_stats (open_interest_usd,
long_liq_usd, short_liq_usd, lsr_taker).
"""
import json, os, sys, time, urllib.request

G = "https://api.gateio.ws/api/v4/futures/usdt"
MARKETS, KEEP_DAYS = 30, 90
COLS = ["t", "sym", "price", "bid1", "ask1", "bid2", "ask2", "spread_bp", "oi_usd", "funding", "liq_long_usd", "liq_short_usd", "lsr_taker"]


def fetch(url, timeout=20, cap=5_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": "futures-radar-snapshot"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(cap).decode("utf-8"))


def num(v):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def depth(bids, asks):
    """bids/asks: [(price, usd)]. Returns (mid, bid1, ask1, bid2, ask2, spread_bp) or None (same maths as bookStats in the app)."""
    bids = sorted([b for b in bids if b[0] > 0 and b[1] > 0], key=lambda x: -x[0])
    asks = sorted([a for a in asks if a[0] > 0 and a[1] > 0], key=lambda x: x[0])
    if not bids or not asks or bids[0][0] >= asks[0][0]:
        return None
    mid = (bids[0][0] + asks[0][0]) / 2
    within = lambda side, pct: sum(u for p, u in side if abs(p / mid - 1) <= pct)
    return (mid, within(bids, 0.01), within(asks, 0.01), within(bids, 0.02), within(asks, 0.02), (asks[0][0] - bids[0][0]) / mid * 1e4)


def merge(prev_rows, new_rows, now):
    cut = now - KEEP_DAYS * 86400
    seen, out = set(), []
    for r in prev_rows + new_rows:
        if not isinstance(r, list) or len(r) != len(COLS) or not isinstance(r[0], int) or r[0] < cut:
            continue
        k = (r[0] // 3600, r[1])
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return sorted(out, key=lambda r: (r[0], r[1]))


def previous():
    repo = os.environ.get("GITHUB_REPOSITORY", "876lab/futures-radar")
    try:
        j = fetch(f"https://raw.githubusercontent.com/{repo}/market-data/market.json", 60, 40_000_000)
        return j.get("rows", []) if j.get("cols") == COLS else []
    except Exception:
        return []


def snapshot(now):
    cons = {c["name"]: c for c in fetch(G + "/contracts") if isinstance(c, dict) and "name" in c}
    ticks = [t for t in fetch(G + "/tickers") if isinstance(t, dict) and t.get("contract") in cons]
    ticks = [t for t in ticks if not cons[t["contract"]].get("in_delisting") and (num(t.get("last")) or 0) > 0]
    ticks.sort(key=lambda t: -(num(t.get("volume_24h_quote")) or 0))
    rows, fails = [], []
    for t in ticks[:MARKETS]:
        sym = t["contract"]
        try:
            q = num(cons[sym].get("quanto_multiplier")) or 1
            ob = fetch(f"{G}/order_book?contract={sym}&limit=100")
            lv = lambda side: [(num(x.get("p")) or 0, (num(x.get("p")) or 0) * (num(x.get("s")) or 0) * q) for x in ob.get(side, []) if isinstance(x, dict)]
            d = depth(lv("bids"), lv("asks"))
            if not d:
                raise ValueError("empty book")
            st = fetch(f"{G}/contract_stats?contract={sym}&interval=1h&limit=1")
            st = st[-1] if isinstance(st, list) and st else {}
            r = lambda v, n=0: None if v is None else round(v, n) if n else int(round(v))
            rows.append([now, sym, num(t.get("last")), r(d[1]), r(d[2]), r(d[3]), r(d[4]), r(d[5], 2),
                         r(num(st.get("open_interest_usd"))), num(t.get("funding_rate")),
                         r(num(st.get("long_liq_usd"))), r(num(st.get("short_liq_usd"))), num(st.get("lsr_taker"))])
        except Exception as e:
            fails.append(f"{sym}: {type(e).__name__}")
        time.sleep(0.15)
    return rows, fails


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "market.json"
    now = int(time.time()) // 3600 * 3600
    rows, fails = snapshot(now)
    if len(rows) < 10:
        print(f"only {len(rows)} markets snapshotted ({fails[:5]}); not publishing")
        sys.exit(1)
    allrows = merge(previous(), rows, now)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"v": 1, "updated": now, "source": "Gate USDT perpetuals", "cols": COLS, "rows": allrows, "fails": fails}, f, separators=(",", ":"))
    print(f"{len(rows)} markets this hour, {len(allrows)} rows kept, {len(fails)} failed")
