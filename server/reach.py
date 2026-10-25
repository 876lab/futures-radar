"""Reach check for the cloud server: one small public request to each data source, recorded with its HTTP status and time.

    python3 server/reach.py OUT.json
Only official public endpoints, no keys:
  Binance USDS-M futures  GET /fapi/v1/time         https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Check-Server-Time
  Bybit V5                GET /v5/market/time        https://bybit-exchange.github.io/docs/v5/market/time
  Gate API v4             GET /futures/usdt/contracts/BTC_USDT  https://www.gate.com/docs/developers/apiv4/
  SEC EDGAR (stock Picks) GET data.sec.gov/submissions          https://www.sec.gov/search-filings/edgar-application-programming-interfaces
"""
import json, platform, socket, sys, time, urllib.request, urllib.error

CHECKS = [
    ("Binance", "https://fapi.binance.com/fapi/v1/time"),
    ("Bybit", "https://api.bybit.com/v5/market/time"),
    ("Gate", "https://api.gateio.ws/api/v4/futures/usdt/contracts/BTC_USDT"),
    ("SEC", "https://data.sec.gov/submissions/CIK0000320193.json"),
]
UA = "futures-radar server (876lab@users.noreply.github.com)"   # the SEC asks for a contact in the User-Agent


def check(name, url):
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(200_000)
            code = r.status
            ok = code == 200 and body[:1] in (b"{", b"[")
            # Bybit answers 200 with retCode != 0 when it refuses a region
            if ok and name == "Bybit":
                ok = json.loads(body).get("retCode") == 0
    except urllib.error.HTTPError as e:
        code, ok = e.code, False
    except Exception as e:   # DNS, timeout, refused
        code, ok = str(type(e).__name__)[:40], False
    return {"name": name, "ok": ok, "code": code, "ms": round((time.time() - t0) * 1000)}


def main(out):
    res = [check(n, u) for n, u in CHECKS]
    doc = {"v": 1, "updated": int(time.time()), "host": socket.gethostname()[:40], "python": platform.python_version(), "checks": res}
    with open(out, "w") as f:
        json.dump(doc, f)
    print("reach: " + ", ".join(f"{c['name']} {'ok' if c['ok'] else 'BLOCKED ' + str(c['code'])}" for c in res))


if __name__ == "__main__":
    main(sys.argv[1])
