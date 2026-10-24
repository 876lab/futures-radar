"""Checks the hourly snapshot job's maths (order-book depth, merging and pruning) without any network."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import snapshot as s

bad = []
def check(c, m):
    if not c: bad.append(m)

d = s.depth([(99.5, 1000), (98.5, 2000), (97, 5000)], [(100.5, 1500), (101.5, 500), (103, 9000)])
check(d is not None and abs(d[0] - 100) < 1e-9, "mid price")
check(d[1] == 1000 and d[2] == 1500, "depth within 1%")
check(d[3] == 3000 and d[4] == 2000, "depth within 2%")
check(abs(d[5] - 100) < 1e-6, "spread in basis points")
check(s.depth([(101, 5)], [(100, 5)]) is None and s.depth([], [(1, 1)]) is None, "crossed or empty book")
now = 1792800000
row = lambda t, sym: [t, sym] + [1] * (len(s.COLS) - 2)
m = s.merge([row(now - 91 * 86400, "OLD_USDT"), row(now - 3600, "BTC_USDT"), ["junk"]], [row(now, "BTC_USDT"), row(now - 3600 + 60, "BTC_USDT")], now)
check([(r[0], r[1]) for r in m] == [(now - 3600, "BTC_USDT"), (now, "BTC_USDT")], "merge drops 90+ days, junk and duplicate hours")
if bad:
    print("snapshot test FAILED:"); [print("  - " + b) for b in bad]; sys.exit(1)
print("snapshot test passed")
