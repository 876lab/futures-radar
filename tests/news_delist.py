"""Checks the news job's delisting-headline parser (tickers, exchanges, dates) without any network."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import fetch_news as f

now = 1792800000  # 23 Oct 2026
bad = []
def check(cond, msg):
    if not cond: bad.append(msg)

check(f.delist_tickers("Binance will delist EPIC and QUICK on October 28") == ["EPIC", "QUICK"], "binance spot headline")
check(f.delist_tickers("Delisting of 1000PEPEUSDT and EPICUSDT Perpetual Contracts") == ["PEPE", "EPIC"], "bybit-style contract names")
check(f.delist_tickers("Bitcoin rallies as ETF inflows grow") == [], "no 'delist' word, no tickers")
check(f.delist_tickers("OKX to delist USDT pairs for MiCA") == [], "stop words and exchange names are not tickers")
check(f.delist_date("Binance will delist EPIC on October 28", now) == 1793145600, "date without year")
check(f.delist_date("Delisting on Jan. 5, 2027", now) == 1799107200, "date with year")
check(f.delist_date("no date here", now) is None, "no date")
m = f.merge_delist([{"t": "Binance will delist EPIC and QUICK on October 28", "u": "https://a.example/1", "s": "CoinDesk", "d": now, "x": ""},
                    {"t": "Bitcoin up", "u": "https://a.example/2", "s": "CoinDesk", "d": now, "x": ""}],
                   [{"t": "old", "u": "https://a.example/old", "s": "X", "d": now - 50 * 86400, "x": ["OLD"]},
                    {"t": "kept", "u": "https://a.example/k", "s": "X", "d": now - 10 * 86400, "x": ["KEEP"]}], now)
check([e["u"] for e in m] == ["https://a.example/1", "https://a.example/k"], "merge keeps new + recent, drops 45+ days and non-delist")
check(m[0]["e"] == ["Binance"] and m[0]["x"] == ["EPIC", "QUICK"], "merge fields")
if bad:
    print("news delist test FAILED:"); [print("  - " + b) for b in bad]; sys.exit(1)
print("news delist test passed")
