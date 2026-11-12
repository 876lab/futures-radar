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
# nightly backtest report: built from the sample data by the real script, plus odds for every bucket so the chart can show one
import subprocess, tempfile
_btf = os.path.join(tempfile.mkdtemp(), "backtest.json")
subprocess.run(["node", os.path.join(ROOT, "..", "scripts", "backtest.js"), PAGE, _btf, "--demo"], check=True, capture_output=True)
BT = json.load(open(_btf)); BT["updated"] = int(time.time()) - 3600
for tf in ("15m", "1h", "4h"):
    for side in ("long", "short"):
        for band in ("70+", "50-69", "<50"):
            for c in ("0", "1"):
                BT["odds"][f"{tf}|{side}|{band}|{c}"] = {"n": 150, "reach": 0.55, "lo": 0.47, "hi": 0.63, "win": 0.5, "avgR": 0.12}
_cyf = os.path.join(tempfile.mkdtemp(), "cycle.json")
subprocess.run(["node", os.path.join(ROOT, "..", "scripts", "cycle.js"), PAGE, _cyf, "--demo"], check=True, capture_output=True)
CY = json.load(open(_cyf)); CY["updated"] = int(time.time()) - 3600
_trf = os.path.join(tempfile.mkdtemp(), "track.json")   # track record replayed hour by hour on sample data by the real script
subprocess.run(["node", os.path.join(ROOT, "..", "scripts", "track.js"), PAGE, _trf, "--demo"], check=True, capture_output=True)
TR = json.load(open(_trf)); TR["updated"] = int(time.time()) - 1800
async def route_bt(pg):
    await pg.route("**/backtest-data/backtest.json*", lambda r: r.fulfill(body=json.dumps(BT), headers={"access-control-allow-origin": "*", "content-type": "application/json"}))
    await pg.route("**/cycle-data/cycle.json*", lambda r: r.fulfill(body=json.dumps(CY), headers={"access-control-allow-origin": "*", "content-type": "application/json"}))
    await pg.route("**/track-data/track.json*", lambda r: r.fulfill(body=json.dumps(TR), headers={"access-control-allow-origin": "*", "content-type": "application/json"}))
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

async def alerts_check(b):
    """Price alerts: set one from the chart's bell, see it on the Starred page, remove it; an alert reached while you were away shows a banner."""
    pg = await b.new_page(viewport={"width": 390, "height": 800})
    await block_exchanges(pg)
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.add_init_script(ACCEPT)
    await pg.goto("file://" + PAGE); await pg.wait_for_timeout(2500)
    key = await pg.get_attribute(".row", "data-key")
    await pg.click(".row"); await pg.wait_for_timeout(1500)
    await pg.click("#dBell"); await pg.wait_for_timeout(200)
    t = await pg.inner_text("#alBox") if await pg.is_visible("#alBox") else ""
    if "Price alert" not in t or "+5%" not in t: problems.append(f"alerts: bell did not open the alert card: {t[:80]!r}")
    await pg.click('#alBox [data-alq]'); await pg.wait_for_timeout(100)
    if "Rings when price" not in await pg.inner_text("#alPrev"): problems.append("alerts: quick price did not fill the box")
    await pg.click('#alForm button[type="submit"]'); await pg.wait_for_timeout(300)
    if await pg.locator("#alBox .al-item").count() != 1: problems.append("alerts: alert not listed after setting it")
    if await pg.get_attribute("#dBell", "aria-pressed") != "true": problems.append("alerts: bell not lit after setting an alert")
    saved = await pg.evaluate("JSON.parse(localStorage.getItem('fradar:alerts')||'[]')")
    if len(saved) != 1 or saved[0].get("k") != key: problems.append(f"alerts: not saved on the device: {saved!r}")
    # a price far from the current one (a typo like $132.90 for $1,132.90) asks first and suggests the likely price
    now = float((await pg.inner_text("#dPrice")).replace("$", "").replace(",", ""))
    await pg.fill("#alIn", str(round(now * 1.012 / 10, 8))); await pg.click('#alForm button[type="submit"]'); await pg.wait_for_timeout(200)
    pv = await pg.inner_text("#alPrev")
    if "Did you mean" not in pv or not await pg.locator("#alPrev [data-alset]").count(): problems.append(f"alerts: far-away price did not ask first: {pv!r}")
    if await pg.locator("#alBox .al-item").count() != 1: problems.append("alerts: far-away price was saved without asking")
    await pg.locator("#alBox").screenshot(path=os.path.join(OUT, "alert-typo.png"))
    await pg.click("#alPrev [data-alset]"); await pg.wait_for_timeout(300)
    if await pg.locator("#alBox .al-item").count() != 2: problems.append("alerts: tapping the suggested price did not set it")
    await pg.click("#alBox .al-item [data-aldel]"); await pg.wait_for_timeout(200)
    await pg.locator("#alBox").screenshot(path=os.path.join(OUT, "alert-card.png"))
    await pg.click("#back"); await pg.wait_for_timeout(400)
    await pg.click('[data-nav="watch"]'); await pg.wait_for_timeout(500)
    lt = await pg.inner_text("#listArea")
    if "Price alerts" not in lt or "1 alert waiting" not in lt: problems.append(f"alerts: Starred page list missing: {lt[:120]!r}")
    for bad in ("undefined", "NaN"):
        if bad in lt: problems.append(f"alerts: Starred page shows '{bad}'")
    # folded by default so it doesn't push the starred markets down (owner report, 12 Nov 2026); one line per market when open
    if await pg.get_attribute("#alList", "open") is not None: problems.append("alerts: Starred list should start folded")
    await pg.click("#alList > summary"); await pg.wait_for_timeout(200)
    if await pg.locator("#alList .al-groups li").count() != 1 or await pg.locator("#alList .al-chip").count() != 1: problems.append("alerts: grouped one-line list missing")
    await pg.screenshot(path=os.path.join(OUT, "alerts-starred.png"))
    await pg.click('#alList [data-aldel]'); await pg.wait_for_timeout(300)
    if await pg.locator("#alList").count(): problems.append("alerts: removing the alert did not clear the list")
    # reached while you were away: an alert made 2 days ago that the sample prices have already passed
    past = int(time.time() * 1000) - 2 * 86400000
    if errs: problems.append("alerts: uncaught JS error: " + errs[0])
    await pg.close()
    pg = await b.new_page(viewport={"width": 390, "height": 800})   # file:// pages don't keep storage across reloads here, so seed it before load
    await block_exchanges(pg)
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.add_init_script(ACCEPT + f"try{{localStorage.setItem('fradar:alerts', JSON.stringify([{{id:'t1',k:{json.dumps(key)},root:'TEST',p:0.0000001,d:1,t:{past},hit:null}}]))}}catch(e){{}}")
    await pg.goto("file://" + PAGE); await pg.wait_for_timeout(3500)
    bar = await pg.inner_text("#alBar") if await pg.is_visible("#alBar") else ""
    if "while you were away" not in bar: problems.append(f"alerts: closed-app check did not show the banner: {bar!r}")
    else: await pg.locator("#alBar").screenshot(path=os.path.join(OUT, "alert-banner.png"))
    if bar:
        await pg.click('#alBar [data-albar="ok"]'); await pg.wait_for_timeout(200)
        if await pg.is_visible("#alBar"): problems.append("alerts: OK did not close the banner")
    if errs: problems.append("alerts: uncaught JS error: " + errs[0])
    await pg.close()

async def stock_check(b):
    """Stock futures: company card with listing exchange and hours on the chart screen; not shown for crypto. 200W EMA chip and legend."""
    for scheme in ("light", "dark"):
        pg = await b.new_page(viewport={"width": 390, "height": 800}, color_scheme=scheme)
        await block_exchanges(pg)
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script(ACCEPT)
        await pg.goto("file://" + PAGE); await pg.wait_for_timeout(2500)
        await pg.click('[data-nav="markets"]'); await pg.wait_for_timeout(500)
        await pg.fill("#q", "tesla"); await pg.wait_for_timeout(500)
        await pg.click(".row"); await pg.wait_for_timeout(1800)
        co = await pg.inner_text("#coBox") if await pg.is_visible("#coBox") else ""
        for want in ("Tesla", "Nasdaq: TSLA", "electric cars", "9:30am", "around the clock", "SEC filings"):
            if want.lower() not in co.lower(): problems.append(f"[{scheme}] stock card: '{want}' missing: {co[:120]!r}")
        if await pg.locator('#coBox a[href*="nasdaq.com/market-activity/stocks/tsla"]').count() != 1: problems.append(f"[{scheme}] stock card: Nasdaq link missing")
        if not await pg.locator('#toggles [data-ind="w200"]').count(): problems.append(f"[{scheme}] chart: 200W EMA chip missing")
        lg = await pg.inner_text("#legend")
        if "EMA 200W" not in lg: problems.append(f"[{scheme}] chart: 200W EMA missing from the legend: {lg[:160]!r}")
        for bad in ("undefined", "NaN"):
            if bad in co or bad in lg: problems.append(f"[{scheme}] stock card or legend shows '{bad}'")
        await pg.locator("#coBox").screenshot(path=os.path.join(OUT, f"stock-card-{scheme}.png"))
        await pg.click("#back"); await pg.wait_for_timeout(300)
        await pg.fill("#q", "bitcoin"); await pg.wait_for_timeout(500)
        await pg.click(".row"); await pg.wait_for_timeout(1200)
        if await pg.is_visible("#coBox"): problems.append(f"[{scheme}] stock card shown on a crypto market")
        if errs: problems.append(f"[{scheme}] stock check: uncaught JS error: " + errs[0])
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

async def mine_check(b):
    # Simulator -> Your trades: import a position-history CSV, see the stats, look up the chart readings, keep and remove them
    for scheme in ("dark", "light"):
        pg = await b.new_page(viewport={"width": 390, "height": 800}, device_scale_factor=1, color_scheme=scheme)
        pg.on("pageerror", lambda e: problems.append(f"[{scheme}] my trades: JS error: {e}"))
        await block_exchanges(pg); await route_bt(pg); await pg.add_init_script(ACCEPT)
        await pg.goto("file://" + PAGE); await pg.wait_for_timeout(2000)
        await pg.click('[data-nav="sim"]'); await pg.wait_for_timeout(500)
        if "Your trades" not in await pg.inner_text("#mineCard"): problems.append(f"[{scheme}] my trades: card missing"); await pg.close(); continue
        await pg.set_input_files("#mineFile", os.path.join(ROOT, "fixtures", "trades.csv")); await pg.wait_for_timeout(500)
        t = await pg.inner_text("#mineCard")
        for want in ("5 trades", "Win rate 60%", "Biggest loss", "SOL long", "Read 5 trades"):
            if want not in t: problems.append(f"[{scheme}] my trades: '{want}' missing after import")
        await pg.click("#mineMore summary"); await pg.click("#mineCheck")
        try: await pg.wait_for_selector("#mineCheck", timeout=60000)
        except Exception: problems.append(f"[{scheme}] my trades: chart-reading check never finished")
        t = await pg.inner_text("#mineCard")
        if "1H chart reading when you opened" not in t or "4H chart reading when you opened" not in t: problems.append(f"[{scheme}] my trades: chart-reading tables missing")
        for bad in ("undefined", "NaN", "Invalid Date", "could not be checked"):
            if bad in t: problems.append(f"[{scheme}] my trades: shows '{bad}'")
        if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, "my-trades.png"), full_page=True)
        saved = await pg.evaluate("localStorage.getItem('fradar:mytrades')||'[]'")
        kept = len([t for t in json.loads(saved) if isinstance(t.get("r1h"), str)])
        if kept != 5: problems.append(f"[{scheme}] my trades: trades or chart readings not saved on the device")
        await pg.close()
        # a fresh start with the saved trades in storage shows them again
        pg = await b.new_page(viewport={"width": 390, "height": 800}, device_scale_factor=1, color_scheme=scheme)
        pg.on("pageerror", lambda e: problems.append(f"[{scheme}] my trades (reopen): JS error: {e}"))
        await block_exchanges(pg); await route_bt(pg); await pg.add_init_script(ACCEPT + ";try{localStorage.setItem('fradar:mytrades'," + json.dumps(saved) + ")}catch(e){}")
        await pg.goto("file://" + PAGE); await pg.wait_for_timeout(1500); await pg.click('[data-nav="sim"]'); await pg.wait_for_timeout(500)
        if "5 trades" not in await pg.inner_text("#mineCard"): problems.append(f"[{scheme}] my trades: saved trades not shown when the app is reopened")
        await pg.evaluate("window.confirm=()=>true")
        await pg.click("#mineClear"); await pg.wait_for_timeout(300)
        if "Choose a CSV file" not in await pg.inner_text("#mineCard"): problems.append(f"[{scheme}] my trades: remove did not work")
        await pg.close()

async def backup_check(b):
    """Back up your data: save a backup file, lose everything, restore it, undo the restore; a wrong file gets a plain message."""
    ctx = await b.new_context(viewport={"width": 390, "height": 800}, accept_downloads=True)
    pg = await ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await block_exchanges(pg)
    seed = ("localStorage.setItem('fradar:terms','1');localStorage.setItem('fradar:watch2',JSON.stringify(['binance:BTCUSDT','gate:ETH_USDT']));"
            "localStorage.setItem('fradar:alerts','[]');localStorage.setItem('fradar:acct','250');localStorage.setItem('fradar:risk','1.5');"
            "localStorage.setItem('fradar:errs','[\"x\"]');")
    await pg.goto("file://" + PAGE); await pg.evaluate(seed); await pg.reload(); await pg.wait_for_timeout(2000)
    await pg.click("#openSettings"); await pg.wait_for_timeout(300)
    if not await pg.is_visible("#backupGrp") or "No backup yet" not in await pg.inner_text("#bkLast"): problems.append("backup: Settings has no 'Back up your data' group")
    async with pg.expect_download() as dl_info: await pg.click("#bkSave")
    dl = await dl_info.value; bf = os.path.join(OUT, "fr-backup.json"); await dl.save_as(bf)
    import re as _re
    if not _re.match(r"^futures-radar-backup-\d{4}-\d\d-\d\d\.json$", dl.suggested_filename): problems.append("backup: file name " + dl.suggested_filename)
    bk = json.load(open(bf))
    if bk.get("app") != "Futures Radar" or bk.get("version") != 1: problems.append("backup: file header wrong")
    d = bk.get("data", {})
    if d.get("watch2") != ["binance:BTCUSDT", "gate:ETH_USDT"] or d.get("acct") != 250 or d.get("risk") != 1.5: problems.append("backup: starred markets or settings missing: " + json.dumps(d)[:200])
    if "errs" in d or "bkLast" in d: problems.append("backup: includes the error log or its own bookkeeping")
    await pg.wait_for_timeout(200)
    if "Last backup: today" not in await pg.inner_text("#bkLast"): problems.append("backup: last-backup line not updated")
    # lose everything, as if the Home Screen icon were removed
    await pg.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('fradar:')).forEach(k=>localStorage.removeItem(k));localStorage.setItem('fradar:terms','1')")
    await pg.reload(); await pg.wait_for_timeout(1500)
    await pg.click("#openSettings"); await pg.wait_for_timeout(300)
    bad = os.path.join(OUT, "not-a-backup.json"); open(bad, "w").write("hello")
    await pg.set_input_files("#bkFile", bad); await pg.wait_for_timeout(300)
    if "isn't a Futures Radar backup" not in await pg.inner_text("#bkPreview"): problems.append("backup: wrong file gets no plain message")
    await pg.set_input_files("#bkFile", bf); await pg.wait_for_timeout(300)
    pv = await pg.inner_text("#bkPreview")
    if "2 starred markets" not in pv or "Restore" not in pv: problems.append("backup: preview missing what the backup holds: " + pv[:120])
    if await pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"): problems.append("backup: Settings wider than a phone screen")
    await pg.locator("#backupGrp").screenshot(path=os.path.join(OUT, "backup.png"))
    async with pg.expect_navigation(): await pg.click("#bkGo")
    await pg.wait_for_timeout(1500)
    st = await pg.evaluate("({w:JSON.parse(localStorage.getItem('fradar:watch2')||'null'),a:localStorage.getItem('fradar:acct'),u:!!localStorage.getItem('fradar:bkUndo')})")
    if st["w"] != ["binance:BTCUSDT", "gate:ETH_USDT"] or st["a"] != "250" or not st["u"]: problems.append("backup: restore did not bring the data back: " + json.dumps(st))
    await pg.click("#openSettings"); await pg.wait_for_timeout(300)
    if not await pg.is_visible("#bkUndo"): problems.append("backup: no Undo restore after restoring")
    async with pg.expect_navigation(): await pg.click("#bkUndo")
    await pg.wait_for_timeout(1500)
    st2 = await pg.evaluate("({w:localStorage.getItem('fradar:watch2'),u:localStorage.getItem('fradar:bkUndo')})")
    if st2["w"] is not None or st2["u"] is not None: problems.append("backup: Undo restore did not go back: " + json.dumps(st2))
    for e in errs: problems.append("backup: JS error: " + e)
    await ctx.close()

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
            await route_bt(pg)
            await pg.add_init_script(ACCEPT)
            await pg.goto("file://" + PAGE); await pg.wait_for_timeout(2500)
            # market light at the top: a colour, a label, and the reasons when tapped
            mlc = await pg.get_attribute("#mlight", "class") or ""
            mls = await pg.inner_text("#mlight summary")
            if not any(k in mlc.split() for k in ("red", "green", "amber", "purple")) or "Market light:" not in mls: problems.append(f"[{scheme}] market light not showing a colour: {mlc!r} {mls!r}")
            await pg.click("#mlight summary"); await pg.wait_for_timeout(200)
            mlb = await pg.inner_text("#mlight .ml-body")
            for want in ("What the light sees now", "RSI 14", "Fear & Greed: 55", "Crypto cycle gauge:", "30 days later", "not financial advice"):
                if want not in mlb: problems.append(f"[{scheme}] market light: '{want}' missing")
            for bad in ("undefined", "NaN", "Infinity", "null"):
                if bad in mlb: problems.append(f"[{scheme}] market light shows '{bad}'")
            await pg.locator("#mlight").screenshot(path=os.path.join(OUT, f"market-light-{scheme}.png"))
            await pg.click("#mlight summary"); await pg.wait_for_timeout(100)
            for nav in ("markets", "setups", "news", "watch", "sim", "markets"):
                await pg.click(f'[data-nav="{nav}"]'); await pg.wait_for_timeout(700)
                txt = await pg.inner_text("#listArea")
                if not txt.strip(): problems.append(f"[{scheme}] {nav}: page is empty")
                for bad in ("undefined", "NaN"):
                    if bad in txt: problems.append(f"[{scheme}] {nav}: shows '{bad}'")
                if nav == "sim" and ("Last night's backtest" not in txt or "Confirmed setups" not in txt or "reached target 1" not in txt): problems.append(f"[{scheme}] simulator: last night's backtest card missing")
                if nav == "sim":
                    await pg.click("#trCard summary"); await pg.wait_for_timeout(150)
                    trt = await pg.inner_text("#trCard")
                    for want in ("Track record", "finished setups", "Open now", "By month started", "Latest finished", "never edited or removed", "every hourly update"):
                        if want not in trt: problems.append(f"[{scheme}] simulator: track record card is missing '{want}'")
                    if scheme == "light":   # CSV download of every finished record
                        try:
                            async with pg.expect_download(timeout=5000) as dl: await pg.click("#trCsv")
                            d = await dl.value; raw = open(await d.path(), encoding="utf-8-sig", newline="").read()
                            lines = raw.split("\r\n")
                            if not d.suggested_filename.startswith("futures-radar-track-record-") or not d.suggested_filename.endswith(".csv"): problems.append(f"simulator: track CSV file name '{d.suggested_filename}'")
                            if not lines[0].startswith("market,candle,side,agreement") or len(lines) - 2 != len(TR["closed"]) or lines[-1] != "": problems.append(f"simulator: track CSV has {len(lines)-2} rows for {len(TR['closed'])} finished records")
                        except Exception as e: problems.append(f"simulator: track CSV download failed: {e}")
                    await pg.locator("#trCard").screenshot(path=os.path.join(OUT, f"track-{scheme}.png"))
                if nav == "news":
                    vx = await pg.inner_text(".card.vix") if await pg.locator(".card.vix").count() else ""
                    if "VIX" not in vx or "20.10" not in vx or "Nervous" not in vx or "fear gauge" not in vx or not await pg.locator(".card.vix svg polyline").count(): problems.append(f"[{scheme}] news: VIX card missing or wrong: {vx[:120]!r}")
                    if scheme == "dark" and vx: await pg.locator(".ntop").screenshot(path=os.path.join(OUT, "vix.png"))
                    ft = await pg.inner_text("#filCard") if await pg.locator("#filCard").count() else ""
                    if "Company earnings filings" not in ft or "SOFI" not in ft or "GOOGL" not in ft or "Quarterly report (10-Q)" not in ft: problems.append(f"[{scheme}] news: company filings card missing")
                    await pg.fill("#filIn", "nvda"); await pg.click("#filAdd button"); await pg.wait_for_timeout(150)
                    if "NVDA" not in await pg.inner_text("#filCard"): problems.append(f"[{scheme}] news: adding a ticker to filings failed")
                    if not await pg.locator('#filCard a[href*="sec.gov/cgi-bin/browse-edgar"][href*="CIK=NVDA"]').count(): problems.append(f"[{scheme}] news: NVDA filing link missing")
                    await pg.click('[data-filrm="NVDA"]'); await pg.wait_for_timeout(150)
                    await pg.locator("#filCard").screenshot(path=os.path.join(OUT, f"filings-{scheme}.png"))
                    cyt = await pg.inner_text("#cyCard") if await pg.locator("#cyCard").count() else ""
                    if "Crypto cycle" not in cyt or "/100" not in cyt or "halving" not in cyt: problems.append(f"[{scheme}] news: crypto cycle gauge missing")
                    await pg.click("#cyCard summary"); await pg.wait_for_timeout(150)
                    cyt = await pg.inner_text("#cyCard")
                    for want in ("200-week", "Mayer", "Pi Cycle", "all-time high"):
                        if want not in cyt: problems.append(f"[{scheme}] cycle gauge: '{want}' missing")
                    if scheme == "dark": await pg.locator("#cyCard").screenshot(path=os.path.join(OUT, "cycle.png"))
                if nav == "setups" and "Crypto cycle:" not in txt: problems.append(f"[{scheme}] setups: crypto cycle line missing")
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
            # Oversold tab: green wave dots in the last 14 days and oversold-now markets, from daily candles
            await pg.click('[data-cat="wave"]'); await pg.wait_for_timeout(2500)
            txt = await pg.inner_text("#listArea")
            if "Green wave dots" not in txt or "Oversold now" not in txt: problems.append(f"[{scheme}] oversold tab: sections missing: {txt[:120]!r}")
            if "Reading daily charts" in txt: problems.append(f"[{scheme}] oversold tab: never finished reading")
            nd = await pg.locator("#listArea .r-note").count()
            if nd > 20: problems.append(f"[{scheme}] oversold tab: more than 10 per list ({nd})")
            for bad in ("undefined", "NaN", "Infinity", "null"):
                if bad in txt: problems.append(f"[{scheme}] oversold tab: shows '{bad}'")
            print(f"  note: [{scheme}] oversold tab shows {nd} markets on sample data")
            for mode in ("", "compact"):   # the note sits under the row's text, never on top of it (owner report, 7 Nov 2026)
                await pg.evaluate(f"document.body.classList.toggle('compact', {'true' if mode else 'false'})"); await pg.wait_for_timeout(200)
                bad = await pg.evaluate("[...document.querySelectorAll('#listArea .row')].filter(r=>r.querySelector('.r-note')).some(r=>{const n=r.querySelector('.r-note').getBoundingClientRect();return [...r.querySelectorAll('.r-main,.r-right,.spark')].some(e=>{const b=e.getBoundingClientRect();return b.height&&n.top<b.bottom-1&&n.bottom>b.top+1&&n.left<b.right-1&&n.right>b.left+1})})")
                if bad: problems.append(f"[{scheme}] oversold tab: note overlaps the row {('in compact mode' if mode else '')}")
            await pg.evaluate("document.body.classList.remove('compact')")
            if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, "oversold.png"))
            await pg.click('[data-cat="heat"]'); await pg.wait_for_timeout(1500)
            txt = await pg.inner_text("#listArea")
            if "Red wave dots" not in txt or "Overheated now" not in txt: problems.append(f"[{scheme}] overheated tab: sections missing: {txt[:120]!r}")
            for bad in ("undefined", "NaN", "Infinity", "null"):
                if bad in txt: problems.append(f"[{scheme}] overheated tab: shows '{bad}'")
            print(f"  note: [{scheme}] overheated tab shows {await pg.locator('#listArea .r-note').count()} markets on sample data")
            if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, "overheated.png"))
            await pg.click('[data-cat="bo"]'); await pg.wait_for_timeout(1500)
            txt = await pg.inner_text("#listArea")
            if "Just broke out" not in txt or "Coiling under resistance" not in txt: problems.append(f"[{scheme}] breakout tab: sections missing: {txt[:120]!r}")
            for bad in ("undefined", "NaN", "Infinity", "null"):
                if bad in txt: problems.append(f"[{scheme}] breakout tab: shows '{bad}'")
            print(f"  note: [{scheme}] breakout tab shows {await pg.locator('#listArea .r-note').count()} markets on sample data")
            if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, "breakout.png"))
            await pg.click('[data-cat="wave"]'); await pg.wait_for_timeout(300)
            await pg.click('[data-cat="hot"]'); await pg.wait_for_timeout(300)
            await pg.click("#openSettings"); await pg.wait_for_timeout(500)
            st = await pg.inner_text("#settings")
            if "max loss per trade" not in st.lower() or "big news warning" not in st.lower(): problems.append(f"[{scheme}] settings page incomplete")
            if "only show confirmed setups" not in st.lower(): problems.append(f"[{scheme}] settings: confirmed-setups switch missing")
            if "About & legal" not in st or await pg.locator("#settings a[href='terms.html'], #settings a[href='risk.html'], #settings a[href='privacy.html']").count() != 3: problems.append(f"[{scheme}] settings: About & legal links missing")
            for bad in ("undefined", "NaN"):
                if bad in st: problems.append(f"[{scheme}] settings: shows '{bad}'")
            if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, "settings.png"), full_page=True)
            if not await pg.is_visible("#setBack"): problems.append(f"[{scheme}] settings: Back button missing")
            else:
                await pg.click("#setBack"); await pg.wait_for_timeout(400)
                if await pg.is_visible("#settings"): problems.append(f"[{scheme}] settings: Back did not leave the page")
                await pg.click("#openSettings"); await pg.wait_for_timeout(400)
            await pg.click('[data-nav="markets"]'); await pg.wait_for_timeout(500)
            if await pg.is_visible("#settings"): problems.append(f"[{scheme}] settings page did not close")
            # sort menu also on Hot; picking a sort opens All sorted that way (owner report, 7 Nov 2026)
            await pg.click('[data-cat="hot"]'); await pg.wait_for_timeout(300)
            if not await pg.is_visible("#sortWrap"): problems.append(f"[{scheme}] hot: sort menu missing")
            else:
                await pg.select_option("#sort", "gain"); await pg.wait_for_timeout(500)
                if await pg.get_attribute('[data-cat="all"]', "aria-selected") != "true": problems.append(f"[{scheme}] hot: sorting did not open All")
                await pg.select_option("#sort", "vol"); await pg.wait_for_timeout(300)
                await pg.click('[data-cat="hot"]'); await pg.wait_for_timeout(300)
            await pg.evaluate("window.scrollBy(0, 300)"); await pg.wait_for_timeout(100)
            if not await pg.evaluate("document.body.classList.contains('nav-away')"): problems.append(f"[{scheme}] bottom bar did not hide while scrolling")
            await pg.wait_for_timeout(800)
            if await pg.evaluate("document.body.classList.contains('nav-away')"): problems.append(f"[{scheme}] bottom bar did not come back after scrolling")
            await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(800)
            await pg.click(".row"); await pg.wait_for_timeout(1500)
            sig = await pg.inner_text("#sigCard")
            if not sig.strip(): problems.append(f"[{scheme}] chart screen: signal card empty")
            if "Big US news" not in sig: problems.append(f"[{scheme}] chart screen: big-news warning missing")
            lg = await pg.inner_text("#legend")
            if "latest" not in lg or not any(d in lg for d in ("Mon,", "Tue,", "Wed,", "Thu,", "Fri,", "Sat,", "Sun,")) or "Invalid" in lg or "%" not in lg: problems.append(f"[{scheme}] chart legend: candle date or % move missing: {lg[:120]!r}")
            if "chart reading ·" not in sig.lower() or "not financial advice" not in sig: problems.append(f"[{scheme}] chart screen: 'Chart reading' label or legal note missing")
            await pg.wait_for_timeout(800)
            if await pg.locator("#mtf [data-mtf]").count() != 4: problems.append(f"[{scheme}] chart screen: candle-size strip missing")
            elif "…" in await pg.inner_text("#mtf"): problems.append(f"[{scheme}] chart screen: candle-size strip never finished loading")
            sig = await pg.inner_text("#sigCard")
            if ("Long setup" in sig or "Short setup" in sig) and "confirmed" not in sig.lower(): problems.append(f"[{scheme}] chart screen: confirmation missing under a setup")
            if "Checking the bigger picture" in sig: problems.append(f"[{scheme}] chart screen: confirmation never finished")
            bk = await pg.inner_text("#bookBox") if await pg.is_visible("#bookBox") else ""
            if "Order book" not in bk or "Within 2% of price" not in bk or "Large" not in bk: problems.append(f"[{scheme}] chart screen: order book card missing")
            for bad in ("undefined", "NaN", "Infinity"):
                if bad in bk: problems.append(f"[{scheme}] order book shows '{bad}'")
            # RSI divergence card (1H/4H/1D only) and chip
            dv = await pg.inner_text("#divBox") if await pg.is_visible("#divBox") else ""
            if "RSI divergence" not in dv or not await pg.locator('#toggles [data-ind="div"]').count(): problems.append(f"[{scheme}] chart: RSI divergence card or chip missing: {dv[:80]!r}")
            # support and resistance card (ladder) and chart lines, switchable with their chip
            srt = await pg.inner_text("#srBox") if await pg.is_visible("#srBox") else ""
            if "Support and resistance" not in srt or "Now" not in srt or not any(x in srt for x in ("S1", "R1")) or "What do these mean?" not in srt: problems.append(f"[{scheme}] chart screen: support/resistance card missing: {srt[:100]!r}")
            for bad in ("undefined", "NaN", "Infinity", "null"):
                if bad in srt: problems.append(f"[{scheme}] support/resistance card shows '{bad}'")
            if not await pg.locator('#toggles [data-ind="sr"]').count(): problems.append(f"[{scheme}] chart: Support/Resistance chip missing")
            if scheme == "light" and srt: await pg.locator("#srBox").screenshot(path=os.path.join(OUT, "support-resistance.png"))
            if await pg.evaluate("!!window.LightweightCharts"):
                if int(await pg.get_attribute("#cMain", "data-sr") or 0) < 1: problems.append(f"[{scheme}] chart: support/resistance lines missing")
                await pg.click('[data-ind="sr"]'); await pg.wait_for_timeout(200)
                if (await pg.get_attribute("#cMain", "data-sr")) != "0": problems.append(f"[{scheme}] chart: Support/Resistance chip did not hide the lines")
                await pg.click('[data-ind="sr"]'); await pg.wait_for_timeout(200)
            # Fibonacci card and chart lines (information only), switchable with the chip above the chart
            fb = await pg.inner_text("#fibBox") if await pg.is_visible("#fibBox") else ""
            if "Fibonacci levels" not in fb or "Next level above" not in fb or "%" not in fb: problems.append(f"[{scheme}] chart screen: Fibonacci card missing")
            for bad in ("undefined", "NaN", "Infinity", "null"):
                if bad in fb: problems.append(f"[{scheme}] Fibonacci card shows '{bad}'")
            if await pg.evaluate("!!window.LightweightCharts"):   # the chart library comes from jsDelivr; some test machines can't reach it
                nfl = int(await pg.get_attribute("#cMain", "data-fib") or 0)
                if nfl < 7: problems.append(f"[{scheme}] chart: Fibonacci lines missing ({nfl})")
                await pg.click('[data-ind="fib"]'); await pg.wait_for_timeout(200)
                if (await pg.get_attribute("#cMain", "data-fib")) != "0": problems.append(f"[{scheme}] chart: Fibonacci chip did not hide the lines")
                await pg.click('[data-ind="fib"]'); await pg.wait_for_timeout(200)
                if scheme == "dark": await pg.locator(".chartbox").screenshot(path=os.path.join(OUT, "fibonacci-chart.png"))
            else: print("  note: chart library unreachable here, Fibonacci chart lines not checked")
            if scheme == "dark" and fb: await pg.locator("#fibBox").screenshot(path=os.path.join(OUT, "fibonacci.png"))
            if ("Long setup" in sig or "Short setup" in sig) and "In last night's backtest" not in sig: problems.append(f"[{scheme}] chart screen: past win rate missing under a setup")
            for old in ("signal ·", "enter long", "enter short", "avoid for now", "confidence", "size this trade"):
                if old in sig.lower(): problems.append(f"[{scheme}] chart screen: old wording '{old}' still shown")
            # weekly and monthly candles: chart and trend only, no entry/stop/targets; back to a normal size afterwards
            was = await pg.get_attribute('#tfSeg [aria-pressed="true"]', "data-tf")
            for big in ("1w", "1M"):
                await pg.click(f'#tfSeg [data-tf="{big}"]'); await pg.wait_for_timeout(1200)
                bs = await pg.inner_text("#sigCard"); lbl = "1W" if big == "1w" else "1M"
                if f"{lbl} candles · trend only".lower() not in bs.lower() or "Entry zone" in bs or "Stop loss" in bs or "Position size" in bs: problems.append(f"[{scheme}] chart {lbl}: trend-only card wrong: {bs[:120]!r}")
                if await pg.get_attribute(f'#tfSeg [data-tf="{big}"]', "aria-pressed") != "true": problems.append(f"[{scheme}] chart {lbl}: button not pressed")
                for bad in ("undefined", "NaN"):
                    if bad in bs: problems.append(f"[{scheme}] chart {lbl}: shows '{bad}'")
                if scheme == "light" and big == "1w": await pg.screenshot(path=os.path.join(OUT, "chart-1w.png"))
                # wave and divergence: on 1W (owner request, 7 Nov 2026), not on 1M
                wv = await pg.inner_text("#waveBox") if await pg.is_visible("#waveBox") else ""
                dv = await pg.inner_text("#divBox") if await pg.is_visible("#divBox") else ""
                hb = await pg.inner_text("#huntBox") if await pg.is_visible("#huntBox") else ""
                if big == "1w":
                    if "1W candles" not in wv and "70 weeks" not in wv: problems.append(f"[{scheme}] chart 1W: wave card missing: {wv[:120]!r}")
                    if "1W" not in dv or "Switch to one of those" in dv: problems.append(f"[{scheme}] chart 1W: divergence card missing: {dv[:120]!r}")
                    if hb and "Switch to one of those" not in hb: problems.append(f"[{scheme}] chart 1W: stop-hunts should stay off weekly")
                    if "day" in wv.replace("1D card", "").replace("daily dots", "").lower().replace("today", ""): problems.append(f"[{scheme}] chart 1W: wave card still says 'day': {wv[:200]!r}")
                    if scheme == "dark" and wv: await pg.locator("#waveBox").screenshot(path=os.path.join(OUT, "wave-1w.png"))
                else:
                    if wv and "Switch to one of those" not in wv: problems.append(f"[{scheme}] chart 1M: wave should not show on monthly")
                    if dv and "Switch to one of those" not in dv: problems.append(f"[{scheme}] chart 1M: divergence should not show on monthly")
                for bad in ("undefined", "NaN", "Infinity"):
                    if bad in wv or bad in dv: problems.append(f"[{scheme}] chart {lbl}: wave/divergence card shows '{bad}'")
            # live track record beside the past win rate (1H and 4H setups only); sample track data has under 100 finished
            seen_tr = False
            for ttf in ("1h", "4h"):
                await pg.click(f'#tfSeg [data-tf="{ttf}"]'); await pg.wait_for_timeout(1500)
                s4 = await pg.inner_text("#sigCard")
                for bad in ("undefined", "NaN"):
                    if bad in s4: problems.append(f"[{scheme}] chart {ttf}: reading shows '{bad}'")
                if ("Long setup" in s4 or "Short setup" in s4) and "Checking the bigger picture" not in s4:
                    seen_tr = True
                    if "Live track record:" not in s4 or "of 100 finished setups" not in s4: problems.append(f"[{scheme}] chart {ttf}: live track record line missing under a setup")
                    if scheme == "light": await pg.locator("#confirm").screenshot(path=os.path.join(OUT, "track-odds.png"))
            if not seen_tr: print(f"  note: [{scheme}] no 1H/4H setup on the test market, live track record line not checked")
            dv = await pg.inner_text("#divBox") if await pg.is_visible("#divBox") else ""
            if "4H candles" not in dv or ("divergence" not in dv.lower()) or "Switch to one of those" in dv: problems.append(f"[{scheme}] chart 4H: divergence card wrong: {dv[:120]!r}")
            for bad in ("undefined", "NaN"):
                if bad in dv: problems.append(f"[{scheme}] divergence card shows '{bad}'")
            if scheme == "light": await pg.locator("#divBox").screenshot(path=os.path.join(OUT, "divergence.png"))
            hb = await pg.inner_text("#huntBox") if await pg.is_visible("#huntBox") else ""
            if "Stop-hunts" not in hb or "4H candles" not in hb or "What is a stop-hunt?" not in hb or not await pg.locator('#toggles [data-ind="hunt"]').count(): problems.append(f"[{scheme}] chart 4H: stop-hunt card or chip wrong: {hb[:120]!r}")
            for bad in ("undefined", "NaN", "Infinity"):
                if bad in hb: problems.append(f"[{scheme}] stop-hunt card shows '{bad}'")
            if scheme == "light": await pg.locator("#huntBox").screenshot(path=os.path.join(OUT, "stop-hunt.png"))
            wv = await pg.inner_text("#waveBox") if await pg.is_visible("#waveBox") else ""
            if not await pg.is_visible("#briefBtn"): problems.append(f"[{scheme}] chart 4H: breakdown button missing")
            else:
                await pg.evaluate("document.querySelector('#briefBtn').click()"); await pg.wait_for_timeout(300)
                b4 = await pg.inner_text("#briefBox")
                if "candles (" not in b4 or "4H reading" not in b4: problems.append(f"[{scheme}] chart 4H: breakdown not worded for 4H candles: {b4[:200]!r}")
                for bad in ("undefined", "NaN", "Infinity", "null", "20-day", "Today's candle"):
                    if bad in b4: problems.append(f"[{scheme}] chart 4H breakdown shows '{bad}'")
                if scheme == "light": await pg.locator("#briefBox").screenshot(path=os.path.join(OUT, "brief-4h.png"))
                await pg.evaluate("document.querySelector('#briefBtn').click()"); await pg.wait_for_timeout(200)
            if "Wave signals" not in wv or "Switch to one of those" not in wv: problems.append(f"[{scheme}] chart 4H: wave card should point to 1D: {wv[:120]!r}")
            await pg.click('#tfSeg [data-tf="1d"]'); await pg.wait_for_timeout(1500)
            wv = await pg.inner_text("#waveBox") if await pg.is_visible("#waveBox") else ""
            if "Wave signals" not in wv or "1D candles" not in wv or "The wave is" not in wv or "How the wave signals work" not in wv or not await pg.locator('#toggles [data-ind="wave"]').count(): problems.append(f"[{scheme}] chart 1D: wave card or chip wrong: {wv[:160]!r}")
            if not await pg.locator("#waveBox svg.wv polyline").count(): problems.append(f"[{scheme}] chart 1D: wave picture missing")
            if "bubble stage" not in wv.lower() or not await pg.locator("#waveBox svg.bub-c circle.dot").count() or "Stages of a bubble" not in wv: problems.append(f"[{scheme}] chart 1D: bubble stage missing")
            if "Holding longer" not in wv or "90 days" not in wv or "random days" not in wv.lower(): problems.append(f"[{scheme}] chart 1D: wave card is missing the 30/60/90-day table")
            if await pg.locator("#waveBox svg.wv text.t").count() < 7: problems.append(f"[{scheme}] chart 1D: wave picture is missing its dates or levels")
            if await pg.locator("#waveBox svg.wv circle").count() and not await pg.locator("#waveBox svg.wv text.dl").count(): problems.append(f"[{scheme}] chart 1D: wave dots have no price labels")
            for bad in ("undefined", "NaN", "Infinity", "null"):
                if bad in wv: problems.append(f"[{scheme}] wave card shows '{bad}'")
            await pg.locator("#waveBox").screenshot(path=os.path.join(OUT, f"wave-{scheme}.png"))
            # chart breakdown button (1D only): closed by default, opens with every section, no broken numbers
            if not await pg.is_visible("#briefBtn"): problems.append(f"[{scheme}] chart 1D: 'Break down this chart' button missing")
            else:
                await pg.evaluate("document.querySelector('#briefBtn').click()"); await pg.wait_for_timeout(300)
                bf = await pg.inner_text("#briefBox")
                for want in ("TREND", "LATEST MOVE", "HOW STRETCHED", "KEY LEVELS", "THE TWO SIDES", "not financial advice"):
                    if want.lower() not in bf.lower(): problems.append(f"[{scheme}] chart breakdown: missing '{want}'")
                for bad in ("undefined", "NaN", "Infinity", "null", "you should"):
                    if bad in bf: problems.append(f"[{scheme}] chart breakdown shows '{bad}'")
                await pg.evaluate("document.querySelector('#briefBox').scrollIntoView()"); await pg.locator("#briefBox").screenshot(path=os.path.join(OUT, f"brief-{scheme}.png"))
                await pg.evaluate("document.querySelector('#briefBtn').click()"); await pg.wait_for_timeout(200)
            await pg.evaluate("document.querySelector('#toggles [data-ind=\"wave\"]').click()"); await pg.wait_for_timeout(300)
            if await pg.is_visible("#waveBox"): problems.append(f"[{scheme}] chart 1D: wave chip did not hide the card")
            await pg.evaluate("document.querySelector('#toggles [data-ind=\"wave\"]').click()"); await pg.wait_for_timeout(300)
            await pg.click(f'#tfSeg [data-tf="{was}"]'); await pg.wait_for_timeout(1200)
            if "chart reading ·" not in (await pg.inner_text("#sigCard")).lower(): problems.append(f"[{scheme}] chart: going back from 1M to {was} did not bring the chart reading back")
            if scheme == "dark":
                await pg.screenshot(path=os.path.join(OUT, "chart.png"))
                await pg.go_back(); await pg.wait_for_timeout(600)   # phone back gesture closes the chart screen
                if await pg.is_visible("#detail .d-head"): problems.append("back did not close the chart screen")
                await pg.click('[data-nav="sim"]'); await pg.wait_for_timeout(400)
                await pg.click("#simRun")
                await pg.wait_for_selector("#simRes", timeout=30000)
                res = await pg.inner_text("#simRes")
                if "NaN" in res or "undefined" in res: problems.append("simulator results show NaN/undefined")
                lab = await pg.inner_text("#labCard")
                if "What the backtest is learning" not in lab or "Today's rules" not in lab or "NaN" in lab or "undefined" in lab: problems.append(f"simulator: lab card wrong: {lab[:160]!r}")
                await pg.locator("#labCard").screenshot(path=os.path.join(OUT, "lab.png"))
                for want in ("Starting with", "trades", "won", "lost", "about even", "Fees and slippage cost", "Latest trades, in plain words", "How a simulated trade works", "More numbers and breakdowns"):
                    if want not in res: problems.append(f"simulator: plain summary missing '{want}'")
                if await pg.is_visible("#simRes .tiles"): problems.append("simulator: detailed numbers should be folded away under 'More numbers'")
                await pg.locator("#simRes").screenshot(path=os.path.join(OUT, "sim-plain.png"))
                await pg.screenshot(path=os.path.join(OUT, "sim.png"), full_page=True)
                # running again with other settings gives a new, numbered result; clear and reset work
                await pg.click('[data-sim="minConf"][data-v="70"]'); await pg.click("#simRun")
                await pg.wait_for_selector("#simRes", timeout=30000)
                if "run 2 at" not in (await pg.inner_text("#simRes")).lower(): problems.append("simulator: second run did not show as a new result")
                await pg.click("#simClear"); await pg.wait_for_timeout(300)
                if await pg.locator("#simRes").count(): problems.append("simulator: Clear results did not clear")
                await pg.click("#simReset"); await pg.wait_for_timeout(300)
                if await pg.get_attribute('[data-sim="minConf"][data-v="0"]', "aria-pressed") != "true": problems.append("simulator: Reset settings did not restore the defaults")
                await pg.click("#openHelp"); await pg.wait_for_timeout(300)
                if not await pg.is_visible("#help"): problems.append("help sheet did not open")
                if await pg.locator("#help .legallinks a").count() != 3: problems.append("help sheet: About & legal links missing")
                # help: opens on "What's new" when there is something new, else on the guide; tabs; Back closes it
                ht = await pg.inner_text("#help")
                if "What's new" not in ht: problems.append("help sheet: What's new missing")
                await pg.click('.htabs [data-htab="guide"]'); await pg.wait_for_timeout(150)
                g = await pg.inner_text('[data-hpanel="guide"]')
                for want in ("Start here", "The four readings", "Long setup", "Wait", "Agreement", "Keep in mind"):
                    if want not in g: problems.append(f"help guide: '{want}' missing")
                await pg.screenshot(path=os.path.join(OUT, "help-guide.png"))
                await pg.click('.htabs [data-htab="terms"]'); await pg.wait_for_timeout(150)
                if not await pg.is_visible('[data-hpanel="terms"] dl'): problems.append("help sheet: Glossary tab did not open")
                await pg.click('.htabs [data-htab="new"]'); await pg.wait_for_timeout(150)
                if not (await pg.inner_text("#whatsNew")).strip() or "Loading" in await pg.inner_text("#whatsNew"): problems.append("help sheet: What's new tab empty or stuck loading")
                await pg.evaluate("document.querySelector('#help .sheet').scrollTop=2000"); await pg.wait_for_timeout(100)
                if not await pg.is_visible("#helpBack"): problems.append("help sheet: Back button not visible after scrolling")
                await pg.click("#helpBack"); await pg.wait_for_timeout(300)
                if await pg.is_visible("#help"): problems.append("help sheet: Back did not close it")
                await pg.click("#openHelp"); await pg.wait_for_timeout(300)
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
        await alerts_check(b)
        await stock_check(b)
        await pull_check(b)
        await legal_check(b)
        await backup_check(b)
        await mine_check(b)
        await b.close()

asyncio.run(main())
if problems:
    print("browser test FAILED:"); [print("  - " + x) for x in problems]; sys.exit(1)
print("browser test passed (dark + light, all pages, chart screen, simulator, my trades, legal pages, before-you-start); screenshots in tests/out/")
