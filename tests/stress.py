"""Stress and security test: feeds the app thousands of markets and hostile data, then checks it stays safe and usable.

What it does (all offline: every exchange, news and WebSocket address is answered by this script):
  * ~3,000 markets across Binance, Gate and Bybit, including names that carry HTML/script payloads and broken numbers
    (NaN, Infinity, negative, empty, missing fields), plus a malformed candle response.
  * A hostile news.json: script payloads in titles, sources, tags, coins and calendar entries; javascript: links.
  * WebSocket floods: hundreds of ticker messages a second, with junk and payloads mixed in.
  * Tampered on-device storage (starred list, settings) with payloads and wrong types.
Fails if any payload runs, a non-http(s) link appears, a JS error is thrown, the page shows NaN/undefined/Infinity,
or the list takes too long to render.
"""
import asyncio, json, math, os, random, sys, time
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out"); os.makedirs(OUT, exist_ok=True)
PAGE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "..", "index.html"))
problems = []
random.seed(7)

# Each payload marks the page if it ever runs. No spaces/quotes so it survives attribute contexts too.
PWN = "document.documentElement.dataset.pw=1"
PAY = [f"<img src=x onerror={PWN}>", f"\"><svg onload={PWN}>", f"'><img src=x onerror={PWN}>", f"</script><script>{PWN}</script>",
       f"javascript:{PWN}", "${alert(1)}", "&lt;b&gt;", "‮\u0000"]
NOWS = int(time.time())

def hdr(ct="application/json"):
    return {"access-control-allow-origin": "*", "content-type": ct}

def num(i):
    """Mostly normal prices, with broken ones mixed in."""
    k = i % 41
    if k == 3: return "NaN"
    if k == 5: return "Infinity"
    if k == 7: return "-12.5"
    if k == 11: return ""
    if k == 13: return None
    if k == 17: return "1e308"
    if k == 19: return "0"
    return f"{10 ** random.uniform(-5, 9):.6g}"

def bad_name(i):
    return PAY[i % len(PAY)]

# ---------- Binance ----------
def binance_info(n):
    syms = []
    for i in range(n):
        base = f"B{i}" if i % 25 else f"B{i}{bad_name(i)}"
        dated = i % 60 == 1
        syms.append({"symbol": f"{base}USDT" + ("_261225" if dated else ""), "status": "TRADING", "baseAsset": base, "quoteAsset": "USDT",
                     "contractType": "CURRENT_QUARTER" if dated else ("PERPETUAL" if i % 50 else bad_name(i)),
                     "underlyingType": "COIN" if i % 30 else ["x"], "underlyingSubType": ["Meme"] if i % 9 == 0 else (bad_name(i) if i % 31 == 0 else []),
                     "onboardDate": (NOWS - i * 86400) * 1000 if i % 70 else "soon", "deliveryDate": (NOWS + 60 * 86400) * 1000 if dated else 0})
    return {"symbols": syms}

def binance_tick(info):
    return [{"symbol": s["symbol"], "lastPrice": num(i), "priceChangePercent": num(i + 1) if i % 12 else "abc", "quoteVolume": num(i + 2)}
            for i, s in enumerate(info["symbols"])]

def binance_prem(info):
    return [{"symbol": s["symbol"], "lastFundingRate": "0.0001" if i % 8 else ("" if i % 16 else "x")} for i, s in enumerate(info["symbols"])]

# ---------- Gate ----------
def gate_contracts(n):
    out = []
    for i in range(n):
        name = f"G{i}_USDT" if i % 25 else f"G{i}{bad_name(i)}_USDT"
        out.append({"name": name, "status": "trading", "in_delisting": False, "contract_type": "" if i % 40 else bad_name(i),
                    "create_time": NOWS - i * 3600 if i % 33 else None, "funding_rate": "0.0001"})
    return out

def gate_tickers(cons):
    return [{"contract": c["name"], "last": num(i), "change_percentage": num(i + 3), "volume_24h_quote": num(i + 4),
             "funding_rate": "x" if i % 29 == 0 else "-0.0002"} for i, c in enumerate(cons)]

# ---------- Bybit ----------
def bybit_inst(n):
    out = []
    for i in range(n):
        sym = f"Y{i}USDT" if i % 25 else f"Y{i}{bad_name(i)}USDT"
        out.append({"symbol": sym, "status": "Trading", "settleCoin": "USDT", "baseCoin": sym[:-4], "quoteCoin": "USDT",
                    "contractType": "LinearPerpetual", "deliveryTime": "0", "launchTime": str((NOWS - i * 7200) * 1000),
                    "symbolType": bad_name(i) if i % 35 == 0 else "", "displayName": bad_name(i + 1), "tags": [bad_name(i + 2)] if i % 3 == 0 else []})
    return {"retCode": 0, "result": {"list": out, "nextPageCursor": ""}}

def bybit_tick(inst):
    return {"retCode": 0, "result": {"list": [{"symbol": c["symbol"], "lastPrice": num(i), "price24hPcnt": num(i + 5),
                                                 "turnover24h": num(i + 6), "fundingRate": "0.0001"} for i, c in enumerate(inst["result"]["list"])]}}

def candles(n=1000, tf=900, broken=False):
    t0 = NOWS - n * tf; p = 100.0; rows = []
    for i in range(n):
        o = p; p = max(0.01, p * (1 + random.gauss(0, 0.01))); h = max(o, p) * 1.003; l = min(o, p) * 0.997
        rows.append((t0 + i * tf, o, h, l, p, random.uniform(1e3, 1e6)))
    if broken:
        rows[5] = (rows[5][0], "NaN", None, "x", 0, -1); rows.append(rows[-1]); rows.insert(10, rows[9])
    return rows

def news_json():
    items = []
    for i in range(250):
        items.append({"t": f"Headline {i} {bad_name(i)}", "u": ["javascript:" + PWN, "JaVaScRiPt:" + PWN, " javascript:" + PWN, "data:text/html,<script>" + PWN + "</script>",
                                                                "https://example.com/a?b=\"><img src=x onerror=" + PWN + ">", "//evil.example/x"][i % 6],
                      "s": bad_name(i + 1), "k": ["crypto", "markets", "official", bad_name(i)][i % 4], "d": NOWS - i * 300 if i % 20 else "yesterday",
                      "x": bad_name(i + 2) * 3, "c": ["BTC", bad_name(i), "ETH"] if i % 2 else bad_name(i), "g": ["Hack", bad_name(i + 3)] if i % 3 else None})
    cal = [{"t": bad_name(i) + " CPI", "c": ["USD", bad_name(i), "JPY"][i % 3], "d": NOWS + 600 + i * 1800 if i % 7 else "x", "i": "High" if i % 2 else bad_name(i),
            "f": bad_name(i + 1), "p": bad_name(i + 2)} for i in range(30)]
    return {"v": 1, "updated": NOWS - 60, "items": items, "fng": {"v": bad_name(1), "l": bad_name(2), "d": NOWS, "prev": "x"}, "calendar": cal,
            "sources": [{"name": bad_name(3), "ok": False, "err": bad_name(4)}]}

async def setup(pg, data):
    async def binance(route):
        u = route.request.url
        if "/exchangeInfo" in u: body = data["binfo"]
        elif "/ticker/24hr" in u: body = data["btick"]
        elif "/premiumIndex" in u: body = data["bprem"]
        elif "/klines" in u: body = [[t * 1000, str(o), str(h), str(l), str(c), "1", 0, str(v)] for t, o, h, l, c, v in candles(broken=True)]
        else: body = {}
        await route.fulfill(body=json.dumps(body), headers=hdr())
    async def gate(route):
        u = route.request.url
        if "/contracts" in u: body = data["gcons"]
        elif "/tickers" in u: body = data["gtick"]
        elif "/candlesticks" in u: body = [{"t": t, "o": str(o), "h": str(h), "l": str(l), "c": str(c), "sum": str(v)} for t, o, h, l, c, v in candles()]
        else: body = []
        await route.fulfill(body=json.dumps(body), headers=hdr())
    async def bybit(route):
        u = route.request.url
        if "/instruments-info" in u: body = data["yinst"]
        elif "/tickers" in u: body = data["ytick"]
        elif "/kline" in u: body = {"retCode": 0, "result": {"list": [[str(t * 1000), str(o), str(h), str(l), str(c), "1", str(v)] for t, o, h, l, c, v in reversed(candles())]}}
        else: body = {"retCode": 0, "result": {}}
        await route.fulfill(body=json.dumps(body), headers=hdr())
    await pg.route("https://fapi.binance.com/**", binance)
    await pg.route("https://api.gateio.ws/**", gate)
    await pg.route("https://api.bybit.com/**", bybit)
    await pg.route("**/news-data/news.json*", lambda r: r.fulfill(body=json.dumps(data["news"]), headers=hdr()))
    await pg.route("**/changes.json*", lambda r: r.fulfill(path=os.path.join(ROOT, "..", "changes.json"), headers=hdr()))

    # WebSocket floods: every stream gets bursts of valid, junk and hostile messages
    bsyms = [s["symbol"] for s in data["binfo"]["symbols"]]; gsyms = [c["name"] for c in data["gcons"]]; ysyms = [c["symbol"] for c in data["yinst"]["result"]["list"]]
    async def flood(ws, make):
        try:
            for k in range(40):
                for m in make(k): ws.send(m)
                await asyncio.sleep(0.05)
        except Exception:
            pass
    def bmsgs(k):
        arr = [{"s": random.choice(bsyms), "c": num(k + j), "P": num(j), "q": num(j + 1)} for j in range(300)]
        return [json.dumps({"stream": "!ticker@arr", "data": arr}), "not json", json.dumps({"stream": bad_name(k), "data": {"x": 1}}),
                json.dumps({"stream": "!markPrice@arr@1s", "data": [{"s": random.choice(bsyms), "r": bad_name(k)}]})]
    def gmsgs(k):
        res = [{"contract": random.choice(gsyms), "last": num(k + j), "change_percentage": num(j), "volume_24h_quote": num(j + 2), "funding_rate": bad_name(j)} for j in range(200)]
        return [json.dumps({"channel": "futures.tickers", "event": "update", "result": res}), json.dumps({"channel": "futures.tickers", "event": "update", "result": bad_name(k)}),
                json.dumps({"channel": "futures.candlesticks", "event": "update", "result": [{"n": bad_name(k), "t": "x", "c": "NaN"}]}), "[]", "null"]
    def ymsgs(k):
        return [json.dumps({"topic": "tickers." + s, "data": {"symbol": s, "lastPrice": num(k + j), "price24hPcnt": num(j), "turnover24h": num(j + 1), "fundingRate": bad_name(j)}})
                for j, s in enumerate(random.sample(ysyms, 50))] + [json.dumps({"topic": 5, "data": None}), json.dumps({"topic": "kline.15." + ysyms[1], "data": bad_name(k)})]
    def ws_handler(make):
        def h(ws):
            ws.on_message(lambda m: None)
            asyncio.ensure_future(flood(ws, make))
        return h
    await pg.route_web_socket("wss://fstream.binance.com/**", ws_handler(bmsgs))
    await pg.route_web_socket("wss://fx-ws.gateio.ws/**", ws_handler(gmsgs))
    await pg.route_web_socket("wss://stream.bybit.com/**", ws_handler(ymsgs))

TAMPER = """
const P='fradar:';const s=(k,v)=>localStorage.setItem(P+k,v);
if(!sessionStorage.getItem('tampered')){sessionStorage.setItem('tampered','1');
s('watch2',JSON.stringify(['%(p)s','B25',null,{a:1},12]));s('acct','"%(p)s"');s('risk','{"x":1}');s('maxLoss','-5');s('view','"%(p)s"');s('sort','"%(p)s"');
s('tf2','"%(p)s"');s('cat3','"%(p)s"');s('mcat','"%(p)s"');s('theme','"%(p)s"');s('ind3','"oops"');s('ntopic','"%(p)s"');s('evAll','"yes"');s('errs','[{"t":"x","where":"%(p)s","msg":"%(p)s"}]');s('compact','not json');s('seen','[1,2]');s('sim','{"tfs":"15m","scope":"%(p)s","risk":"x"}');}
""" % {"p": PAY[0].replace("'", "\\'")}

async def check_page(pg, where):
    if await pg.evaluate("document.documentElement.dataset.pw==='1'"): problems.append(f"{where}: a script payload RAN (XSS)")
    bad_links = await pg.evaluate("""[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')).filter(h=>!/^(https?:\\/\\/|#|mailto:|(terms|risk|privacy)\\.html$)/i.test(h.trim()))""")
    if bad_links: problems.append(f"{where}: unsafe link(s): {bad_links[:3]}")
    injected = await pg.evaluate("document.querySelectorAll('#listArea img[src=x], #listArea svg[onload], body script:not([src])').length")
    if injected > 1: problems.append(f"{where}: {injected} injected elements found in the page")
    txt = await pg.evaluate("document.body.innerText")
    for bad in ("undefined", "NaN", "Infinity", "[object Object]"):
        if bad in txt:
            i = txt.index(bad); problems.append(f"{where}: shows '{bad}' near: " + txt[max(0, i - 60):i + 20].replace(chr(10), " | "))

async def main():
    data = {}
    data["binfo"] = binance_info(900); data["btick"] = binance_tick(data["binfo"]); data["bprem"] = binance_prem(data["binfo"])
    data["gcons"] = gate_contracts(1400); data["gtick"] = gate_tickers(data["gcons"])
    data["yinst"] = bybit_inst(700); data["ytick"] = bybit_tick(data["yinst"]); data["news"] = news_json()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for scheme in ("dark", "light"):
            pg = await b.new_page(viewport={"width": 390, "height": 800}, color_scheme=scheme)
            errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("dialog", lambda d: (problems.append(f"[{scheme}] a dialog opened: {d.message}"), asyncio.ensure_future(d.dismiss())))
            await pg.add_init_script("try{localStorage.setItem('fradar:terms','1')}catch(e){}")   # skip 'Before you start'
            await pg.add_init_script(TAMPER)
            await setup(pg, data)
            t0 = time.time()
            await pg.goto("file://" + PAGE)
            try:
                await pg.wait_for_function("(t=>t&&!/Loading markets|Reading charts/.test(t))(document.querySelector('#listArea').innerText)", timeout=20000)
            except Exception:
                problems.append(f"[{scheme}] market list never rendered")
            load_s = time.time() - t0
            await pg.wait_for_timeout(2500)
            mode = await pg.inner_text("#live")
            n_rows = await pg.locator(".row").count()
            if scheme == "dark": print(f"  load to list ready: {load_s:.1f}s; rows on screen: {n_rows}; status: {mode.strip()}")
            if load_s > 10: problems.append(f"[{scheme}] list took {load_s:.1f}s to render with ~3,000 markets")
            await check_page(pg, f"[{scheme}] markets")
            # responsiveness while the WebSocket flood runs: time a search keystroke round trip
            t1 = time.time(); await pg.fill("#q", "B2"); await pg.wait_for_timeout(50); await pg.evaluate("new Promise(r=>requestAnimationFrame(()=>r()))")
            lag = time.time() - t1
            if scheme == "dark": print(f"  search response during flood: {lag*1000:.0f} ms")
            if lag > 1.5: problems.append(f"[{scheme}] search took {lag:.1f}s during the price flood")
            await pg.fill("#q", PAY[0]); await pg.wait_for_timeout(400); await check_page(pg, f"[{scheme}] search with payload")
            await pg.fill("#q", ""); await pg.wait_for_timeout(300)
            for nav in ("setups", "news", "watch", "sim", "markets"):
                try: await pg.click(f'[data-nav="{nav}"]', timeout=8000)
                except Exception:
                    await pg.screenshot(path=os.path.join(OUT, f"stress-fail-{scheme}-{nav}.png")); problems.append(f"[{scheme}] could not open {nav} (see stress-fail-{scheme}-{nav}.png)"); continue
                await pg.wait_for_timeout(900)
                await check_page(pg, f"[{scheme}] {nav}")
                if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, f"stress-{nav}.png"))
            # news topic chips and the hostile market's chart
            await pg.click('[data-nav="news"]'); await pg.wait_for_timeout(500)
            for chip in await pg.locator("#listArea [data-topic]").all():
                try: await chip.click(timeout=1000); await pg.wait_for_timeout(150)
                except Exception: pass
            await check_page(pg, f"[{scheme}] news topics")
            await pg.click('[data-nav="markets"]'); await pg.wait_for_timeout(500)
            await pg.fill("#q", "G25"); await pg.wait_for_timeout(500)
            if await pg.locator(".row").count():
                await pg.locator(".row").first.click(); await pg.wait_for_timeout(2000)
                await check_page(pg, f"[{scheme}] chart of a hostile market")
                if scheme == "dark": await pg.screenshot(path=os.path.join(OUT, "stress-chart.png"))
                await pg.go_back(); await pg.wait_for_timeout(500)
            if scheme == "dark":   # simulator over the hostile markets
                await pg.click('[data-nav="sim"]'); await pg.wait_for_timeout(400); await pg.click("#simRun")
                try:
                    await pg.wait_for_selector("#simRes", timeout=60000); await check_page(pg, f"[{scheme}] simulator results")
                except Exception: problems.append(f"[{scheme}] simulator never finished on hostile data")
            await pg.click("#openSettings"); await pg.wait_for_timeout(400); await check_page(pg, f"[{scheme}] settings")
            heap = await pg.evaluate("performance.memory?Math.round(performance.memory.usedJSHeapSize/1048576):0")
            if scheme == "dark": print(f"  JS heap after flood: {heap} MB")
            if heap > 400: problems.append(f"[{scheme}] memory use {heap} MB after the flood")
            for e in errs: problems.append(f"[{scheme}] JS error: {e}")
            await pg.close()
        await b.close()

asyncio.run(main())
if problems:
    seen = []; [seen.append(x) for x in problems if x not in seen]
    print("stress test FAILED:"); [print("  - " + x) for x in seen[:60]]; sys.exit(1)
print("stress test passed (~3,000 markets, hostile data, WebSocket flood, tampered storage, both themes)")
