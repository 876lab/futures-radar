// Public track record (ROADMAP: monetization step 1). Runs hourly on GitHub.
// Records every Long setup / Short setup the app's own engine (sliced from index.html, like scripts/backtest.js) shows
// on 1H and 4H for the busiest Gate USDT perpetuals, then scores each one on later candles with the Simulator's rules.
// Finished records are copied forward unchanged on every run: never edited, never removed, losses included.
//   node scripts/track.js index.html out/track.json          live Gate data; reads the previous out/track.json if present
//   node scripts/track.js index.html out/track.json --demo   replays sample candles hour by hour, no network (tests)
// TRACK_EXISTING=1 (set by the workflow when the track-data branch already exists) makes a missing or unreadable file fatal,
// so a read problem can never silently restart the record.
'use strict';
const fs = require('fs');
const [, , PAGE = 'index.html', OUT = 'track.json', MODE] = process.argv;
const DEMO = MODE === '--demo';
const src = fs.readFileSync(PAGE, 'utf8');
const cut = (a, b) => { const i = src.indexOf(a), j = src.indexOf(b); if (i < 0 || j < 0 || j < i) throw new Error('marker missing: ' + (i < 0 ? a : b)); return src.slice(i, j); };
global.location = { hostname: '876lab.github.io', pathname: '/futures-radar/' };
const engine = cut('const DAY', '/* ---------- network').replace(/const LS=.*\n/, 'const LS={get:(k,d)=>d,set(){}};\n') +
  cut('/* ---------- sample data', '/* ---------- loading') + cut('/* ---------- indicators', '/* ---------- charts');

const MARKETS = 25, TFS_REC = ['1h', '4h'], LIMIT = 400, LOOKBACK = 3 * 3600;   // setups whose candle closed in the last 3 hours
const OPTS = { plan: 'split', minConf: 0, fee: 0.0005, slip: 0.0002, maxHold: 96 };
const G = 'https://api.gateio.ws/api/v4/futures/usdt';
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function getJSON(url) {
  for (let k = 0; k < 3; k++) {
    try { const r = await fetch(url, { headers: { 'user-agent': 'futures-radar-track' } }); if (r.ok) return await r.json(); if (r.status < 500 && r.status !== 429) throw new Error('HTTP ' + r.status); }
    catch (e) { if (k === 2) throw e; }
    await sleep(1500 * (k + 1));
  }
}

// eslint-disable-next-line no-eval
eval(engine + `
async function gateMarkets() {
  const [cons, ticks] = await Promise.all([getJSON(G + '/contracts'), getJSON(G + '/tickers')]);
  const bad = new Set((cons || []).filter(c => c.in_delisting || /delist|clos/i.test(c.status || '')).map(c => c.name));
  return (ticks || []).filter(t => t && typeof t.contract === 'string' && !bad.has(t.contract) && +t.last > 0)
    .sort((a, b) => (+b.volume_24h_quote || 0) - (+a.volume_24h_quote || 0)).slice(0, MARKETS).map(t => t.contract);
}
async function gateCandles(sym, tf) {
  const m = baseInfo(sym.split('_')[0]).mult || 1;   // same scaling as the app: prices per one unit of the coin
  const r = await getJSON(G + '/candlesticks?contract=' + encodeURIComponent(sym) + '&interval=' + tf + '&limit=' + LIMIT);
  return (Array.isArray(r) ? r : []).map(k => ({ time: +k.t, open: k.o / m, high: k.h / m, low: k.l / m, close: k.c / m, volume: +k.sum || +k.v || 0 }))
    .filter(k => k.time > 0 && k.high > 0 && k.low > 0 && k.open > 0).sort((a, b) => a.time - b.time);
}
const ROOT = {}, rootOf = sym => ROOT[sym] || canonical(baseInfo(sym.split('_')[0]).root);   // coin name shown in the app
const closedAt = (cs, tf, now) => cs.filter(k => k.time + TFS[tf] <= now);
// trend direction (same rule as the chart reading) of the last fully closed candle at time 'at'
function dirAt(cs, tf, at) {
  const c = cs ? cs.filter(k => k.time + TFS[tf] <= at) : [];
  if (c.length < 40) return null;
  const an = analyzeAt(c, computeSeries(c), c.length - 1);
  return an ? recommend(an, c, null, '1d', true).dir : null;
}
// one hourly run: score open records, then record new setups. Pure apart from its inputs (raw candles per market, 'now').
function step(prev, data, now, syms) {
  const open = [], closed = prev.closed.slice(), newIds = [];
  const lastExit = {};
  for (const r of closed) { const k = r.sym + '|' + r.tf; lastExit[k] = Math.max(lastExit[k] || 0, r.t1 || 0); }
  for (const r of prev.open) {
    const raw = data[r.sym] && data[r.sym][r.tf], cs = raw ? closedAt(raw, r.tf, now) : null;
    const i = cs ? cs.findIndex(k => k.time === r.t) : -1;
    if (i < 0) {   // market data missing: after the longest hold plus a day, close it as unscored instead of keeping it open forever
      if (now > r.t0 + (OPTS.maxHold + 1) * TFS[r.tf] + 86400) closed.push(Object.assign({}, r, { how: 'nodata', r: null, reach: false, t1: now }));
      else open.push(r);
      continue;
    }
    const t = simTrade(cs, i, { dir: r.dir, conf: r.conf, levels: { R: r.R } }, OPTS);
    if (!t || t.unfinished) { open.push(r); continue; }
    closed.push(Object.assign({}, r, { r: +t.r.toFixed(3), reach: t.mfe >= 1.5, how: t.how, t1: t.t1, bars: t.bars, exit: +t.exit.toPrecision(8) }));
    lastExit[r.sym + '|' + r.tf] = Math.max(lastExit[r.sym + '|' + r.tf] || 0, t.t1);
  }
  const busy = new Set(open.map(r => r.sym + '|' + r.tf)), seen = new Set(prev.open.map(r => r.id).concat(closed.map(r => r.id)));
  for (const sym of syms) {
    const d = data[sym]; if (!d) continue;
    for (const tf of TFS_REC) {
      const raw = d[tf]; if (!raw) continue;
      const cs = closedAt(raw, tf, now), key = sym + '|' + tf; if (cs.length < SIM_WARM) continue;
      const S = computeSeries(cs), hcs = d[HTF[tf]] ? closedAt(d[HTF[tf]], HTF[tf], now) : [];
      const from = cs.findIndex(k => k.time + TFS[tf] >= now - LOOKBACK); if (from < 0) continue;
      for (let i = Math.max(SIM_WARM, from); i < cs.length; i++) {
        if (busy.has(key) || cs[i].time < (lastExit[key] || 0)) continue;   // one record at a time per market and candle size, like the Simulator
        const id = key + '|' + cs[i].time; if (seen.has(id)) continue;
        const close = cs[i].time + TFS[tf], next = raw.find(k => k.time === close); if (!next) continue;   // entry = next candle's open
        const an = analyzeAt(cs, S, i); if (!an) continue;
        const hc = hcs.filter(k => k.time + TFS[HTF[tf]] <= close), han = hc.length >= 35 ? analyzeAt(hc, computeSeries(hc), hc.length - 1) : null;
        const rc = recommend(an, cs.slice(0, i + 1), han, tf, true);
        if ((rc.rec !== 'long' && rc.rec !== 'short') || !(rc.levels && rc.levels.R > 0)) continue;
        let hi = -Infinity, lo = Infinity, vol = 0;
        for (let k = i; k >= 0 && cs[k].time > close - 86400; k--) { hi = Math.max(hi, cs[k].high); lo = Math.min(lo, cs[k].low); vol += cs[k].volume; }
        const dirs = { '4h': dirAt(d['4h'], '4h', close), '1d': dirAt(d['1d'], '1d', close) };
        const cf = confirmSetup({ dir: rc.dir, tf, dirs, range: lo > 0 && isFinite(hi) ? hi / lo - 1 : null, vol, delisting: false });
        const entry = next.open * (1 + rc.dir * OPTS.slip), R = rc.levels.R, p = x => +x.toPrecision(8);
        open.push({ id, sym, m: rootOf(sym), tf, dir: rc.dir, conf: rc.conf, confirmed: !!cf.ok, t: cs[i].time, t0: close,
          entry: p(entry), stop: p(entry - rc.dir * R), tp1: p(entry + rc.dir * 1.5 * R), tp2: p(entry + rc.dir * 3 * R), R: p(R), seen: now });
        busy.add(key); seen.add(id); newIds.push(id);
      }
    }
  }
  return { open, closed, newIds };
}
function readPrev(must) {
  if (!fs.existsSync(OUT)) { if (must) throw new Error(OUT + ' is missing although the track-data branch exists; not starting over'); return null; }
  const j = JSON.parse(fs.readFileSync(OUT, 'utf8'));
  if (!j || !Array.isArray(j.open) || !Array.isArray(j.closed) || !(j.start > 0)) throw new Error(OUT + ' is not a track record; not starting over');
  return j;
}
function save(rec, meta) {
  fs.writeFileSync(OUT, JSON.stringify(Object.assign({ v: 1, source: 'Gate USDT perpetuals', tfs: TFS_REC, plan: OPTS.plan, fee: OPTS.fee, slip: OPTS.slip, maxHold: OPTS.maxHold }, meta,
    { open: rec.open, closed: rec.closed })));
}
async function live() {
  const now = Math.floor(Date.now() / 1000), prev = readPrev(process.env.TRACK_EXISTING === '1') || { start: now, runs: 0, open: [], closed: [] };
  const top = await gateMarkets(); if (top.length < 10) throw new Error('Gate returned only ' + top.length + ' markets');
  const syms = [...new Set(top.concat(prev.open.map(r => r.sym)))], data = {}, fails = [];
  for (const sym of syms) {
    try { data[sym] = {}; for (const tf of ['1h', '4h', '1d']) { data[sym][tf] = await gateCandles(sym, tf); await sleep(120); } }
    catch (e) { delete data[sym]; fails.push(sym + ': ' + String(e && e.message || e).slice(0, 80)); }
  }
  if (fails.length > syms.length / 2) throw new Error('too many markets failed: ' + fails.join('; '));
  const rec = step(prev, data, now, top);
  save(rec, { start: prev.start, updated: now, runs: (prev.runs || 0) + 1, markets: top.map(rootOf), fails });
  console.log('track: ' + rec.newIds.length + ' new, ' + rec.open.length + ' open, ' + rec.closed.length + ' finished (' + (rec.closed.length - prev.closed.length) + ' this run); ' + fails.length + ' markets failed');
}
function demo() {
  state.pairs = demoPairs();
  const ps = state.pairs.filter(p => p.kind === 'perp').slice(0, 8), full = {}, end = Math.floor(NOW() / 1000 / 3600) * 3600;
  for (const p of ps) { ROOT[p.sym] = p.root; full[p.sym] = {}; for (const tf of ['1h', '4h', '1d']) full[p.sym][tf] = demoCandles(p, tf, tf === '1h' ? 1200 : 600); }
  let rec = { start: end - 20 * 86400, open: [], closed: [] }, frozen = new Map(), runs = 0;
  for (let now = end - 20 * 86400 + 720; now <= end; now += 3600) {   // runs at minute 12, like the workflow
    const data = {};   // what an hourly run at 'now' could see: candles that had opened by then, the last few hundred
    for (const s in full) { data[s] = {}; for (const tf in full[s]) data[s][tf] = full[s][tf].filter(k => k.time < now).slice(-LIMIT); }
    rec = step(rec, data, now, Object.keys(full)); runs++;
    for (const r of rec.closed) { const j = JSON.stringify(r); if (!frozen.has(r.id)) frozen.set(r.id, j); else if (frozen.get(r.id) !== j) throw new Error('a finished record changed: ' + r.id); }
    if (frozen.size !== rec.closed.length) throw new Error('a finished record disappeared');
    if (new Set(rec.open.map(r => r.sym + '|' + r.tf)).size !== rec.open.length) throw new Error('two open records on one market and candle size');
  }
  for (const r of rec.closed) if (!(r.how === 'nodata' || (isFinite(r.r) && r.t1 >= r.t0 && r.t0 > r.t)) || Math.sign(r.tp1 - r.entry) !== r.dir) throw new Error('bad record ' + JSON.stringify(r));
  if (rec.closed.length < 5) throw new Error('demo produced too few finished records: ' + rec.closed.length);
  save(rec, { source: 'sample data', start: end - 20 * 86400, updated: end, runs, markets: [...new Set(ps.map(p => p.root))], fails: [] });
  console.log('track demo: ' + runs + ' hourly runs, ' + rec.closed.length + ' finished, ' + rec.open.length + ' open; finished records never changed');
}
if (DEMO) demo(); else live().catch(e => { console.error('track failed: ' + (e && e.stack || e)); process.exit(1); });
`);
