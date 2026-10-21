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

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for scheme in ("dark", "light"):
            pg = await b.new_page(viewport={"width": 390, "height": 800}, device_scale_factor=1, color_scheme=scheme)
            pg.on("pageerror", lambda e: problems.append(f"[{scheme}] JS error: {e}"))
            fx = json.load(open(FIX)); fx["updated"] = int(time.time()) - 300
            await pg.route("**/news-data/news.json*", lambda r: r.fulfill(body=json.dumps(fx), headers={"access-control-allow-origin": "*", "content-type": "application/json"}))
            await pg.route("**/changes.json*", lambda r: r.fulfill(path=os.path.join(ROOT, "..", "changes.json"), headers={"content-type": "application/json"}))
            await pg.goto("file://" + PAGE); await pg.wait_for_timeout(2500)
            for nav in ("markets", "setups", "news", "watch", "sim", "markets"):
                await pg.click(f'[data-nav="{nav}"]'); await pg.wait_for_timeout(700)
                txt = await pg.inner_text("#listArea")
                if not txt.strip(): problems.append(f"[{scheme}] {nav}: page is empty")
                for bad in ("undefined", "NaN"):
                    if bad in txt: problems.append(f"[{scheme}] {nav}: shows '{bad}'")
                if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, f"{nav}.png"))
            await pg.click(".row"); await pg.wait_for_timeout(1500)
            sig = await pg.inner_text("#sigCard")
            if not sig.strip(): problems.append(f"[{scheme}] chart screen: signal card empty")
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
            await pg.close()
        await b.close()

asyncio.run(main())
if problems:
    print("browser test FAILED:"); [print("  - " + x) for x in problems]; sys.exit(1)
print("browser test passed (dark + light, all pages, chart screen, simulator); screenshots in tests/out/")
