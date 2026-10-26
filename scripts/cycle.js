// Crypto cycle gauge (information only): Bitcoin's daily history from Gate (BTC/USDT spot), scored with the app's own
// cycleAt / cyclePhase (sliced from index.html, like tests/engine.js), written to cycle.json for the News page.
//   node scripts/cycle.js index.html out/cycle.json          live Gate data (GitHub Actions)
//   node scripts/cycle.js index.html out/cycle.json --demo   built-in sample candles, no network (tests)
'use strict';
const fs = require('fs');
const [, , PAGE = 'index.html', OUT = 'cycle.json', MODE] = process.argv;
const DEMO = MODE === '--demo';
const src = fs.readFileSync(PAGE, 'utf8');
const cut = (a, b) => { const i = src.indexOf(a), j = src.indexOf(b); if (i < 0 || j < 0 || j < i) throw new Error('marker missing: ' + (i < 0 ? a : b)); return src.slice(i, j); };
global.location = { hostname: '876lab.github.io', pathname: '/futures-radar/' };
const engine = cut('const DAY', '/* ---------- network').replace(/const LS=.*\n/, 'const LS={get:(k,d)=>d,set(){}};\n') +
  cut('/* ---------- sample data', '/* ---------- loading') + cut('/* ---------- indicators', '/* ---------- charts');
const G = 'https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=BTC_USDT&interval=1d';
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function getJSON(url) {
  for (let k = 0; k < 3; k++) {
    try { const r = await fetch(url, { headers: { 'user-agent': 'futures-radar-cycle' } }); if (r.ok) return await r.json(); if (r.status < 500 && r.status !== 429) throw new Error('HTTP ' + r.status + ' ' + (await r.text()).slice(0, 120)); }
    catch (e) { if (k === 2) throw e; }
    await sleep(1500 * (k + 1));
  }
}

// eslint-disable-next-line no-eval
eval(engine + `
// Gate spot candles: [time, quote volume, close, high, low, open, base volume, closed] (strings); at most 1000 per request
function parseGate(r) {
  return (Array.isArray(r) ? r : []).map(k => Array.isArray(k) ? { time: +k[0], close: +k[2], high: +k[3], low: +k[4], open: +k[5] }
    : { time: +k.t, close: +k.c, high: +k.h, low: +k.l, open: +k.o }).filter(k => k.time > 0 && k.close > 0 && k.high > 0);
}
async function gateHistory() {
  const now = Math.floor(Date.now() / 1000), step = 900 * 86400, out = new Map();
  for (let from = Date.UTC(2013, 0, 1) / 1000; from < now; from += step) {
    const to = Math.min(now, from + step - 86400);
    let r; try { r = await getJSON(G + '&from=' + from + '&to=' + to); } catch (e) { console.error('window ' + new Date(from * 1000).toISOString().slice(0, 10) + ': ' + e.message); continue; }
    for (const k of parseGate(r)) out.set(k.time, k);
    await sleep(250);
  }
  return [...out.values()].sort((a, b) => a.time - b.time);
}
const day = s => new Date(s * 1000).toISOString().slice(0, 10);
// the gauge on past turning points, so the app can show how it read then (only dates the data covers)
const MARKS = [['Top', '2017-12-17'], ['Low', '2018-12-15'], ['Top', '2021-11-10'], ['Low', '2022-11-21']];
function report(cs) {
  const L = cs.length - 1, now = cycleAt(cs, L);
  if (!now || now.score == null) throw new Error('not enough history (' + cs.length + ' days)');
  const hist = [];
  for (let i = L; i >= 0; i -= 7) { const c = cycleAt(cs, i); if (c && c.score != null) hist.push([c.t, c.score, +c.price.toPrecision(6)]); }
  hist.reverse();
  const marks = [];
  for (const [k, d] of MARKS) { const t = Date.parse(d) / 1000, i = cs.findIndex(x => x.time >= t);
    if (i > 0 && cs[i].time - t < 3 * 86400) { const c = cycleAt(cs, i); if (c && c.score != null) marks.push({ k, d, s: c.score, p: +c.price.toPrecision(6) }); } }
  // the latest all-time high counts as a top once price is 20% or more below it
  if (now.athT && now.price < now.ath * 0.8) { const i = cs.findIndex(x => x.time === now.athT), c = i >= 0 ? cycleAt(cs, i) : null;
    if (c && c.score != null && !marks.some(m => m.d === day(now.athT))) marks.push({ k: 'Top', d: day(now.athT), s: c.score, p: +c.price.toPrecision(6) }); }
  const ph = cyclePhase(now.t * 1000);
  const m = {}; for (const k in now.m) m[k] = now.m[k] ? { v: +now.m[k].v.toFixed(4), s: now.m[k].s } : null;
  return { v: 1, updated: Math.floor(Date.now() / 1000), source: DEMO ? 'sample data' : 'Gate BTC/USDT daily', from: cs[0].time, days: cs.length,
    t: now.t, price: now.price, ath: now.ath, athT: now.athT, score: now.score, m,
    phase: ph && { k: ph.k, name: ph.name, days: ph.days, toNext: ph.toNext }, marks, hist };
}
async function main() {
  let cs;
  if (DEMO) { const p = demoPairs().find(x => x.root === 'BTC'); cs = demoCandles(p, '1d', 2600); }
  else cs = await gateHistory();
  if (!DEMO && cs.length < 1500) throw new Error('only ' + cs.length + ' days of history; not publishing');
  const r = report(cs);
  fs.writeFileSync(OUT, JSON.stringify(r));
  console.log('cycle: ' + r.days + ' days from ' + day(r.from) + '; score ' + r.score + ' (' + cycleZone(r.score)[1] + '); ' +
    Object.entries(r.m).map(([k, v]) => k + ' ' + (v ? v.v.toFixed(2) + '→' + v.s : '—')).join(', ') + '; phase ' + (r.phase && r.phase.name + ' day ' + r.phase.days) +
    '; past turning points ' + r.marks.map(x => x.k + ' ' + x.d + ' = ' + x.s).join(', '));
}
main().catch(e => { console.error('cycle failed: ' + (e && e.stack || e)); process.exit(1); });
`);
