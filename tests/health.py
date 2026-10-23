"""Daily health check of the LIVE app (https://876lab.github.io/futures-radar/).

Runs on GitHub's servers, which are in the US: Binance and Bybit refuse US connections, so they are reported
as "not checkable from here" rather than as failures. Everything else must work:
  - the web page loads and has no JavaScript errors
  - the Markets page lists markets from at least one exchange (Gate answers from the US)
  - Setups, Simulator, News and Starred pages render, without 'undefined' or 'NaN'
  - News headlines are fresh (the news job runs every 15 minutes)
  - the app recorded no problems in its own App health log
Exit code 1 (and a list of problems) if anything is wrong.
"""
import asyncio, json, os, sys, time, urllib.request
from playwright.async_api import async_playwright

SITE = os.environ.get("SITE", "https://876lab.github.io/futures-radar/")
NEWS = "https://raw.githubusercontent.com/876lab/futures-radar/news-data/news.json"
UA = "FuturesRadarHealth/1.0 (+https://github.com/876lab/futures-radar)"
problems, notes = [], []


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


def check_apis():
    try:
        _, body = get(NEWS + "?t=" + str(int(time.time())))
        d = json.loads(body); age = (time.time() - d.get("updated", 0)) / 3600
        if age > 3: problems.append(f"News is {age:.1f} hours old (the news job may be failing)")
        if len(d.get("items", [])) < 10: problems.append(f"News has only {len(d.get('items', []))} headlines")
        dead = [s["name"] for s in d.get("sources", []) if not s.get("ok")]
        if dead: notes.append("News sources not answering: " + ", ".join(dead))
    except Exception as e:
        problems.append(f"News data unreadable: {e}")
    for name, url, min_n in [("Gate", "https://api.gateio.ws/api/v4/futures/usdt/contracts", 100),
                             ("Binance", "https://fapi.binance.com/fapi/v1/exchangeInfo", 1),
                             ("Bybit", "https://api.bybit.com/v5/market/tickers?category=linear", 1)]:
        try:
            _, body = get(url); d = json.loads(body)
            n = len(d) if isinstance(d, list) else len(d.get("symbols") or (d.get("result") or {}).get("list") or [])
            if n < min_n: problems.append(f"{name} answered but listed only {n} markets")
            else: notes.append(f"{name}: OK ({n} markets)")
        except urllib.error.HTTPError as e:
            if name != "Gate" and e.code in (403, 451): notes.append(f"{name}: not checkable from GitHub's US servers (HTTP {e.code})")
            else: problems.append(f"{name} API failed: HTTP {e.code}")
        except Exception as e:
            problems.append(f"{name} API failed: {e}")


async def check_app():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 390, "height": 800})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        resp = await pg.goto(SITE + "?health=" + str(int(time.time())))
        if not resp or resp.status != 200:
            problems.append(f"Web page did not load (status {resp.status if resp else 'none'})"); await b.close(); return
        await pg.wait_for_timeout(9000)
        if not await pg.is_visible("#legal"): problems.append("'Before you start' sheet did not show on first visit")
        else: await pg.click("#legalOk"); await pg.wait_for_timeout(300)
        for name in ("terms", "risk", "privacy"):
            r = await pg.request.get(SITE + name + ".html")
            if r.status != 200: problems.append(f"{name}.html did not load (status {r.status})")
        mode = await pg.inner_text("#live")
        if "Sample" in mode: problems.append("App fell back to sample data: no exchange could be reached from a browser")
        for nav in ("markets", "setups", "sim", "news", "watch"):
            await pg.click(f'[data-nav="{nav}"]'); await pg.wait_for_timeout(2500 if nav == "news" else 1200)
            txt = await pg.inner_text("#listArea")
            if not txt.strip(): problems.append(f"{nav} page is empty")
            if "hit a snag" in txt: problems.append(f"{nav} page shows 'hit a snag'")
            for bad in ("undefined", "NaN"):
                if bad in txt: problems.append(f"{nav} page shows '{bad}'")
            if nav == "markets" and not await pg.locator(".row").count(): problems.append("Markets page lists no markets")
            if nav == "news" and not await pg.locator(".nitem").count(): problems.append("News page shows no headlines")
        await pg.click('[data-nav="markets"]'); await pg.wait_for_timeout(800)
        if await pg.locator(".row").count():
            await pg.click(".row"); await pg.wait_for_timeout(6000)
            sig = await pg.inner_text("#sigCard")
            if "snag" in sig or not sig.strip(): problems.append("Chart screen signal card failed")
        log = await pg.evaluate("localStorage.getItem('fradar:errs')")
        for x in json.loads(log or "[]"): problems.append(f"App health log: [{x.get('where')}] {x.get('msg')}")
        for e in errs[:5]: problems.append("JavaScript error: " + e)
        await b.close()


check_apis()
asyncio.run(check_app())
report = ["Futures Radar daily health check", ""] + (["PROBLEMS:"] + ["  - " + x for x in problems] if problems else ["All checks passed."]) + ["", "Notes:"] + ["  - " + x for x in notes]
print("\n".join(report))
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f: f.write("\n".join(report).replace("PROBLEMS:", "### Problems") + "\n")
sys.exit(1 if problems else 0)
