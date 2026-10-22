"""Headless browser smoke test: loads index.html at phone size and walks every page.

Fails on any JavaScript error, on 'undefined'/'NaN' showing in the page, or if a page renders empty.
Screenshots go to tests/out/ (not committed) for a quick visual check.
"""
import asyncio, json, os, sys, time
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out"); os.makedirs(OUT, exist_ok=True)
PAGE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "..", "index.html"))
FIX = os.path.join(ROOT, "fixtures", "news.json")
problems = []

async def block_exchanges(pg):
    # always use the built-in sample markets, so results don't depend on which exchanges this machine can reach
    for host in ("fapi.binance.com", "api.gateio.ws", "api.bybit.com"):
        await pg.route(f"https://{host}/**", lambda r: r.abort())

async def isolation_check(b):
    """A broken section must show a 'hit a snag' card, be logged in Settings, and leave the other pages working."""
    pg = await b.new_page(viewport={"width": 390, "height": 800})
    await block_exchanges(pg)
    # bad news data is now cleaned on arrival, so break the News page another way: its calendar date formatting throws
    bad = {"updated": int(time.time()), "items": [], "sources": [], "calendar": [{"t": "CPI m/m", "c": "USD", "d": int(time.time()) + 7200, "i": "High"}]}
    await pg.add_init_script("Date.prototype.toLocaleString=function(){throw new Error('test: deliberately broken News page')}")
    await pg.route("**/news-data/news.json*", lambda r: r.fulfill(body=json.dumps(bad), headers={"access-control-allow-origin": "*", "content-type": "application/json"}))
    await pg.route("**/changes.json*", lambda r: r.fulfill(path=os.path.join(ROOT, "..", "changes.json"), headers={"content-type": "application/json"}))
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("file://" + PAGE); await pg.wait_for_timeout(2500)
    await pg.click('[data-nav="news"]'); await pg.wait_for_timeout(1500)
    if "hit a snag" not in await pg.inner_text("#listArea"): problems.append("isolation: broken News page did not show the snag card")
    await pg.click('[data-nav="markets"]'); await pg.wait_for_timeout(700)
    if not await pg.locator(".row").count(): problems.append("isolation: Markets stopped working after News broke")
    await pg.click("#openSettings"); await pg.wait_for_timeout(300)
    if "1 problem recorded" not in await pg.inner_text("#errBox"): problems.append("isolation: problem not recorded in Settings")
    await pg.screenshot(path=os.path.join(OUT, "settings-health.png"))
    if errs: problems.append("isolation: uncaught JS error: " + errs[0])
    await pg.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for scheme in ("dark", "light"):
            pg = await b.new_page(viewport={"width": 390, "height": 800}, device_scale_factor=1, color_scheme=scheme)
            pg.on("pageerror", lambda e: problems.append(f"[{scheme}] JS error: {e}"))
            fx = json.load(open(FIX)); fx["updated"] = int(time.time()) - 300
            fx["calendar"] = [{"t": "CPI m/m", "c": "USD", "d": int(time.time()) + 900, "i": "High", "f": "0.3%", "p": "0.4%"}]   # big news in 15 min
            await pg.route("**/news-data/news.json*", lambda r: r.fulfill(body=json.dumps(fx), headers={"access-control-allow-origin": "*", "content-type": "application/json"}))
            await pg.route("**/changes.json*", lambda r: r.fulfill(path=os.path.join(ROOT, "..", "changes.json"), headers={"content-type": "application/json"}))
            await block_exchanges(pg)
            await pg.goto("file://" + PAGE); await pg.wait_for_timeout(2500)
            for nav in ("markets", "setups", "news", "watch", "sim", "markets"):
                await pg.click(f'[data-nav="{nav}"]'); await pg.wait_for_timeout(700)
                txt = await pg.inner_text("#listArea")
                if not txt.strip(): problems.append(f"[{scheme}] {nav}: page is empty")
                for bad in ("undefined", "NaN"):
                    if bad in txt: problems.append(f"[{scheme}] {nav}: shows '{bad}'")
                if nav == "setups" and "Big US news" not in txt: problems.append(f"[{scheme}] setups: big-news warning missing")
                if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, f"{nav}.png"))
            await pg.click("#openSettings"); await pg.wait_for_timeout(500)
            st = await pg.inner_text("#settings")
            if "max loss per trade" not in st.lower() or "big news warning" not in st.lower(): problems.append(f"[{scheme}] settings page incomplete")
            for bad in ("undefined", "NaN"):
                if bad in st: problems.append(f"[{scheme}] settings: shows '{bad}'")
            if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, "settings.png"), full_page=True)
            await pg.click('[data-nav="markets"]'); await pg.wait_for_timeout(500)
            if await pg.is_visible("#settings"): problems.append(f"[{scheme}] settings page did not close")
            await pg.evaluate("window.scrollBy(0, 300)"); await pg.wait_for_timeout(100)
            if not await pg.evaluate("document.body.classList.contains('nav-away')"): problems.append(f"[{scheme}] bottom bar did not hide while scrolling")
            await pg.wait_for_timeout(800)
            if await pg.evaluate("document.body.classList.contains('nav-away')"): problems.append(f"[{scheme}] bottom bar did not come back after scrolling")
            await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(800)
            await pg.click(".row"); await pg.wait_for_timeout(1500)
            sig = await pg.inner_text("#sigCard")
            if not sig.strip(): problems.append(f"[{scheme}] chart screen: signal card empty")
            if "Big US news" not in sig: problems.append(f"[{scheme}] chart screen: big-news warning missing")
            if scheme == "dark":
                await pg.screenshot(path=os.path.join(OUT, "chart.png"))
                await pg.go_back(); await pg.wait_for_timeout(600)   # phone back gesture closes the chart screen
                if await pg.is_visible("#detail .d-head"): problems.append("back did not close the chart screen")
                await pg.click('[data-nav="sim"]'); await pg.wait_for_timeout(400)
                await pg.click("#simRun")
                await pg.wait_for_selector("#simRes", timeout=30000)
                res = await pg.inner_text("#simRes")
                if "NaN" in res or "undefined" in res: problems.append("simulator results show NaN/undefined")
                await pg.screenshot(path=os.path.join(OUT, "sim.png"), full_page=True)
                await pg.click("#openHelp"); await pg.wait_for_timeout(300)
                if not await pg.is_visible("#help"): problems.append("help sheet did not open")
            # "big news later today" line on Setups: an event 90 min out (skipped late in the local day, when it would fall after midnight)
            if await pg.evaluate("new Date().getHours() < 22"):
                fx["calendar"] = [{"t": "FOMC Statement", "c": "USD", "d": int(time.time()) + 5400, "i": "High", "f": "", "p": ""}]
                await pg.reload(); await pg.wait_for_timeout(2000)
                await pg.click('[data-nav="setups"]'); await pg.wait_for_timeout(1000)
                txt = await pg.inner_text("#listArea")
                if "big news later today" not in txt.lower() or "FOMC Statement" not in txt or "Big US news" in txt: problems.append(f"[{scheme}] setups: 'big news later today' line missing")
                if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, "setups-later.png"))
            await pg.close()
        await isolation_check(b)
        await b.close()

asyncio.run(main())
if problems:
    print("browser test FAILED:"); [print("  - " + x) for x in problems]; sys.exit(1)
print("browser test passed (dark + light, all pages, chart screen, simulator); screenshots in tests/out/")
