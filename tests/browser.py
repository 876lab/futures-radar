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
ACCEPT = "try{localStorage.setItem('fradar:terms','1')}catch(e){}"   # 'Before you start' already accepted (legal_check tests the sheet itself)

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
    await pg.add_init_script(ACCEPT)
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

async def pull_check(b):
    """Pull to refresh: a short pull does nothing; a long pull at the top shows 'Release to refresh' and reloads."""
    pg = await b.new_page(viewport={"width": 390, "height": 800}, has_touch=True, is_mobile=True)
    await block_exchanges(pg)
    await pg.route("**/news-data/news.json*", lambda r: r.fulfill(path=FIX, headers={"access-control-allow-origin": "*", "content-type": "application/json"}))
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.add_init_script(ACCEPT)
    await pg.goto("file://" + PAGE); await pg.wait_for_timeout(2500)
    await pg.evaluate("""window.__fire=(type,y)=>{const t=new Touch({identifier:1,target:document.body,clientX:200,clientY:y});
      document.body.dispatchEvent(new TouchEvent(type,{touches:type==='touchend'?[]:[t],changedTouches:[t],bubbles:true,cancelable:true}))};
      window.__pull=(d)=>{__fire('touchstart',150);for(let y=150;y<=150+d;y+=10)__fire('touchmove',y)}""")
    await pg.evaluate("__pull(60)")
    if "Release" in await pg.inner_text("#ptr"): problems.append("pull to refresh: a short pull already says release")
    await pg.evaluate("__fire('touchend',210)"); await pg.wait_for_timeout(100)
    if await pg.evaluate("document.getElementById('ptr').classList.contains('busy')"): problems.append("pull to refresh: a short pull refreshed")
    await pg.wait_for_timeout(400)
    await pg.evaluate("__pull(220)")
    if "Release to refresh" not in await pg.inner_text("#ptr"): problems.append("pull to refresh: long pull does not say 'Release to refresh'")
    if scheme_shot: await pg.screenshot(path=os.path.join(OUT, "pull.png"))
    await pg.evaluate("__fire('touchend',370)"); await pg.wait_for_timeout(50)
    if "Refreshing" not in await pg.inner_text("#ptr"): problems.append("pull to refresh: release did not start a refresh")
    await pg.wait_for_timeout(1500)
    if await pg.evaluate("getComputedStyle(document.getElementById('ptr')).opacity") != "0": problems.append("pull to refresh: indicator did not go away")
    if not await pg.locator(".row").count() and "Setups" not in await pg.inner_text("#nav"): problems.append("pull to refresh: page empty after refresh")
    for e in errs: problems.append("pull to refresh: JS error: " + e)
    await pg.close()
scheme_shot = True

async def legal_check(b):
    """Terms/Risk/Privacy pages load in both themes; 'Before you start' shows once, and still lets you in without storage."""
    for scheme in ("dark", "light"):
        for name, title in (("terms", "Terms of Use"), ("risk", "Risk Disclosure"), ("privacy", "Privacy Notice")):
            pg = await b.new_page(viewport={"width": 390, "height": 800}, color_scheme=scheme)
            errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto("file://" + os.path.join(os.path.dirname(PAGE), name + ".html"))
            txt = await pg.inner_text("body")
            if title not in txt or "Last updated" not in txt or "Version 0.1" not in txt: problems.append(f"[{scheme}] {name}.html: title, date or version missing")
            if name != "privacy" and "not financial" not in txt.lower() and "not advice" not in txt.lower(): problems.append(f"{name}.html: no 'not advice' statement")
            if await pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"): problems.append(f"[{scheme}] {name}.html: wider than a phone screen")
            if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, f"{name}.png"))
            for e in errs: problems.append(f"{name}.html: JS error: " + e)
            await pg.close()
    pg = await b.new_page(viewport={"width": 390, "height": 800})
    await block_exchanges(pg)
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("file://" + PAGE); await pg.wait_for_timeout(2000)
    if not await pg.is_visible("#legal"): problems.append("'Before you start' sheet did not show on first launch")
    else:
        t = await pg.inner_text("#legal")
        if "not advice" not in t or "I understand" not in t: problems.append("'Before you start' sheet text incomplete")
        if await pg.locator("#legal a[href='terms.html'], #legal a[href='risk.html'], #legal a[href='privacy.html']").count() != 3: problems.append("'Before you start' sheet: links missing")
        await pg.screenshot(path=os.path.join(OUT, "before-you-start.png"))
        await pg.click("#legalOk"); await pg.wait_for_timeout(200)
        if await pg.is_visible("#legal"): problems.append("'I understand' did not close the sheet")
    await pg.reload(); await pg.wait_for_timeout(1500)
    if await pg.is_visible("#legal"): problems.append("'Before you start' showed again after accepting")
    await pg.evaluate("localStorage.setItem('fradar:terms','0')"); await pg.reload(); await pg.wait_for_timeout(1500)
    if not await pg.is_visible("#legal"): problems.append("'Before you start' did not show again for a new terms version")
    for e in errs: problems.append("legal: JS error: " + e)
    await pg.close()
    # no storage at all (private mode / blocked): the sheet shows and the app can still be used
    pg = await b.new_page(viewport={"width": 390, "height": 800})
    await block_exchanges(pg)
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})")
    await pg.goto("file://" + PAGE); await pg.wait_for_timeout(2000)
    if not await pg.is_visible("#legal"): problems.append("no storage: 'Before you start' did not show")
    else:
        await pg.click("#legalOk"); await pg.wait_for_timeout(200)
        if await pg.is_visible("#legal"): problems.append("no storage: could not continue past 'Before you start'")
        await pg.click('[data-nav="setups"]'); await pg.wait_for_timeout(500)
    for e in errs: problems.append("no storage: JS error: " + e)
    await pg.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for scheme in ("dark", "light"):
            pg = await b.new_page(viewport={"width": 390, "height": 800}, device_scale_factor=1, color_scheme=scheme)
            pg.on("pageerror", lambda e: problems.append(f"[{scheme}] JS error: {e}"))
            fx = json.load(open(FIX)); fx["updated"] = int(time.time()) - 300
            fx["calendar"] = [{"t": "CPI m/m", "c": "USD", "d": int(time.time()) + 900, "i": "High", "f": "0.3%", "p": "0.4%"}]   # big news in 15 min
            fx["delist"] = [{"t": "Binance will delist TAO and FOO on October 30", "u": "https://example.com/delist-tao", "s": "CoinDesk", "d": int(time.time()) - 3600, "x": ["TAO", "FOO"], "e": ["Binance"], "at": None}]
            await pg.route("**/news-data/news.json*", lambda r: r.fulfill(body=json.dumps(fx), headers={"access-control-allow-origin": "*", "content-type": "application/json"}))
            await pg.route("**/changes.json*", lambda r: r.fulfill(path=os.path.join(ROOT, "..", "changes.json"), headers={"content-type": "application/json"}))
            await block_exchanges(pg)
            await pg.add_init_script(ACCEPT)
            await pg.goto("file://" + PAGE); await pg.wait_for_timeout(2500)
            for nav in ("markets", "setups", "news", "watch", "sim", "markets"):
                await pg.click(f'[data-nav="{nav}"]'); await pg.wait_for_timeout(700)
                txt = await pg.inner_text("#listArea")
                if not txt.strip(): problems.append(f"[{scheme}] {nav}: page is empty")
                for bad in ("undefined", "NaN"):
                    if bad in txt: problems.append(f"[{scheme}] {nav}: shows '{bad}'")
                if nav == "setups" and "Big US news" not in txt: problems.append(f"[{scheme}] setups: big-news warning missing")
                if nav == "setups" and ("Long setups" not in txt or "Short setups" not in txt): problems.append(f"[{scheme}] setups: 'Long setups'/'Short setups' headings missing")
                for old in ("Enter long", "Enter short", "Avoid for now", "Long entries", "Confidence", "confidence"):
                    if old in txt: problems.append(f"[{scheme}] {nav}: old wording '{old}' still shown")
                if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, f"{nav}.png"))
            # Delisting tab: the two sample delistings, soonest first, with exchange and date; the chart screen warns
            await pg.click('[data-cat="delist"]'); await pg.wait_for_timeout(500)
            txt = await pg.inner_text("#listArea")
            if "ZKJ" not in txt or "KAITO" not in txt or "Binance" not in txt or "Gate" not in txt or "Delists" not in txt: problems.append(f"[{scheme}] delisting tab: sample delistings missing")
            elif txt.index("ZKJ") > txt.index("KAITO"): problems.append(f"[{scheme}] delisting tab: not soonest first")
            if "reduce-only from" not in txt: problems.append(f"[{scheme}] delisting tab: Gate reduce-only time missing")
            if "Announced delistings" not in txt or "Binance will delist TAO" not in txt: problems.append(f"[{scheme}] delisting tab: announced delisting from the news missing")
            for bad in ("undefined", "NaN", "Invalid Date"):
                if bad in txt: problems.append(f"[{scheme}] delisting tab: shows '{bad}'")
            if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, "delisting.png"))
            await pg.click(".dlrow"); await pg.wait_for_timeout(1200)
            if "will delist" not in await pg.inner_text("#dlBox"): problems.append(f"[{scheme}] chart screen: delisting warning missing")
            if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, "delisting-chart.png"))
            await pg.go_back(); await pg.wait_for_timeout(500)
            await pg.click('[data-cat="all"]'); await pg.wait_for_timeout(400)
            if not await pg.locator(".row .tag.dl").count(): problems.append(f"[{scheme}] markets: Delisting tag missing on rows")
            await pg.click('[data-cat="hot"]'); await pg.wait_for_timeout(300)
            await pg.click("#openSettings"); await pg.wait_for_timeout(500)
            st = await pg.inner_text("#settings")
            if "max loss per trade" not in st.lower() or "big news warning" not in st.lower(): problems.append(f"[{scheme}] settings page incomplete")
            if "only show confirmed setups" not in st.lower(): problems.append(f"[{scheme}] settings: confirmed-setups switch missing")
            if "About & legal" not in st or await pg.locator("#settings a[href='terms.html'], #settings a[href='risk.html'], #settings a[href='privacy.html']").count() != 3: problems.append(f"[{scheme}] settings: About & legal links missing")
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
            if "chart reading ·" not in sig.lower() or "not financial advice" not in sig: problems.append(f"[{scheme}] chart screen: 'Chart reading' label or legal note missing")
            await pg.wait_for_timeout(800)
            if await pg.locator("#mtf [data-mtf]").count() != 4: problems.append(f"[{scheme}] chart screen: candle-size strip missing")
            elif "…" in await pg.inner_text("#mtf"): problems.append(f"[{scheme}] chart screen: candle-size strip never finished loading")
            sig = await pg.inner_text("#sigCard")
            if ("Long setup" in sig or "Short setup" in sig) and "extra checks" not in sig.lower(): problems.append(f"[{scheme}] chart screen: extra confirmation missing under a setup")
            if "Running extra checks" in sig: problems.append(f"[{scheme}] chart screen: extra checks never finished")
            for old in ("signal ·", "enter long", "enter short", "avoid for now", "confidence", "size this trade"):
                if old in sig.lower(): problems.append(f"[{scheme}] chart screen: old wording '{old}' still shown")
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
                if await pg.locator("#help a[href='terms.html'], #help a[href='risk.html'], #help a[href='privacy.html']").count() != 3: problems.append("help sheet: About & legal links missing")
                await pg.click('[data-close="help"]'); await pg.wait_for_timeout(200)
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
        await pull_check(b)
        await legal_check(b)
        await b.close()

asyncio.run(main())
if problems:
    print("browser test FAILED:"); [print("  - " + x) for x in problems]; sys.exit(1)
print("browser test passed (dark + light, all pages, chart screen, simulator, legal pages, before-you-start); screenshots in tests/out/")
