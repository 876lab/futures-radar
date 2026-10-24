// Nightly backtest report (ROADMAP: win-odds research, step 1).
// Runs the app's own engine (sliced from index.html, like tests/engine.js) over recent Gate USDT-perpetual candles,
// records the conditions at every simulated entry and writes backtest.json for the Simulator page.
//   node scripts/backtest.js index.html out/backtest.json          live Gate data (GitHub Actions)
//   node scripts/backtest.js index.html out/backtest.json --demo   built-in sample candles, no network (tests)
// Binance and Bybit refuse GitHub's US servers, so only Gate is used. Historical delistings are unknown (counted as none),
// and 24h volume is Gate's alone (the app adds all exchanges), so the liquidity check here is stricter than in the app.
'use strict';
const fs = require('fs');
const [, , PAGE = 'index.html', OUT = 'backtest.json', MODE] = process.argv;
const DEMO = MODE === '--demo';
const src = fs.readFileSync(PAGE, 'utf8');
const cut = (a, b) => { const i = src.indexOf(a), j = src.indexOf(b); if (i < 0 || j < 0 || j < i) throw new Error('marker missing: ' + (i < 0 ? a : b)); return src.slice(i, j); };
global.location = { hostname: '876lab.github.io', pathname: '/futures-radar/' };
const engine = cut('const DAY', '/* ---------- network').replace(/const LS=.*\n/, 'const LS={get:(k,d)=>d,set(){}};\n') +
  cut('/* ---------- sample data', '/* ---------- loading') + cut('/* ---------- indicators', '/* ---------- charts');

const MARKETS = 30, TFS_RUN = ['15m', '1h', '4h'], LIMIT = { '15m': 2000, '1h': 2000, '4h': 2000, '1d': 1000 };
const OPTS = { plan: 'split', minConf: 0, fee: 0.0005, slip: 0.0002, maxHold: 96 };
const G = 'https://api.gateio.ws/api/v4/futures/usdt';
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function getJSON(url) {
  for (let k = 0; k < 3; k++) {
    try { const r = await fetch(url, { headers: { 'user-agent': 'futures-radar-backtest' } }); if (r.ok) return await r.json(); if (r.status < 500 && r.status !== 429) throw new Error('HTTP ' + r.status); }
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
    .sort((a, b) => (+b.volume_24h_quote || 0) - (+a.volume_24h_quote || 0)).slice(0, MARKETS)
    .map(t => ({ ex: 'gate', sym: t.contract, root: t.contract.split('_')[0], id: 'gate:' + t.contract }));
}
async function gateCandles(sym, tf) {
  let r;
  try { r = await getJSON(G + '/candlesticks?contract=' + encodeURIComponent(sym) + '&interval=' + tf + '&limit=' + LIMIT[tf]); }
  catch (e) { r = await getJSON(G + '/candlesticks?contract=' + encodeURIComponent(sym) + '&interval=' + tf + '&limit=1000'); }
  return (Array.isArray(r) ? r : []).map(k => ({ time: +k.t, open: +k.o, high: +k.h, low: +k.l, close: +k.c, volume: +k.sum || +k.v || 0 }))
    .filter(k => k.time > 0 && k.high > 0 && k.low > 0).sort((a, b) => a.time - b.time);
}
// trend direction (same rule as the chart reading) of the last fully closed candle at time 'at'
function dirAt(cs, S, cache, step, at) {
  let lo = 0, hi = cs.length - 1, j = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (cs[m].time + step <= at) { j = m; lo = m + 1; } else hi = m - 1; }
  if (j < 34) return null;
  if (!cache.has(j)) { const an = analyzeAt(cs, S, j); cache.set(j, an ? recommend(an, cs, null, '1d', true).dir : null); }
  return cache.get(j);
}
function runMarket(m, c) {
  const out = [];
  const big = { '4h': c['4h'], '1d': c['1d'] }, BS = {}, BC = { '4h': new Map(), '1d': new Map() };
  for (const k of ['4h', '1d']) BS[k] = big[k] && big[k].length > 40 ? computeSeries(big[k]) : null;
  for (const tf of TFS_RUN) {
    const cs = c[tf], hcs = c[HTF[tf]]; if (!cs || cs.length < SIM_WARM + 20) continue;
    const S = computeSeries(cs), step = TFS[tf];
    const onEntry = (t, x) => {
      const i = x.i, close = cs[i].time + step, price = cs[i].close;
      let hi = -Infinity, lo = Infinity, vol = 0;
      for (let k = i; k >= 0 && cs[k].time > close - 86400; k--) { hi = Math.max(hi, cs[k].high); lo = Math.min(lo, cs[k].low); vol += cs[k].volume; }
      const range = lo > 0 && isFinite(hi) ? hi / lo - 1 : null;
      const dirs = { '4h': BS['4h'] ? dirAt(big['4h'], BS['4h'], BC['4h'], TFS['4h'], close) : null, '1d': BS['1d'] ? dirAt(big['1d'], BS['1d'], BC['1d'], TFS['1d'], close) : null };
      const cf = confirmSetup({ dir: t.dir, tf, dirs, range, vol, delisting: false });
      const r6 = S.r6[i], up = S.bb.up[i], lb = S.bb.lo[i], e20 = S.e20[i], A = x.an.atr || price * 0.01;
      const vs = cs.slice(Math.max(0, i - 20), i).map(k => k.volume), va = vs.reduce((a, b) => a + b, 0) / Math.max(1, vs.length);
      const d = new Date(t.t0 * 1000);
      out.push({ m: m.root, tf, dir: t.dir, conf: t.conf, t0: t.t0, r: +t.r.toFixed(3), reach: t.mfe >= 1.5, how: t.how, bars: t.bars,
        confirmed: cf.ok, d4h: dirs['4h'], d1d: dirs['1d'], range: range == null ? null : +range.toFixed(4), vol: Math.round(vol),
        adx: x.an.adx == null ? null : +x.an.adx.toFixed(1), score: x.an.score, htf: x.han ? (x.han.score >= 20 ? 1 : x.han.score <= -20 ? -1 : 0) : null,
        r6: r6 == null ? null : +r6.toFixed(1), pctB: up != null && up > lb ? +((price - lb) / (up - lb)).toFixed(3) : null,
        ext: e20 != null ? +((price - e20) / A).toFixed(2) : null, vRatio: va ? +(cs[i].volume / va).toFixed(2) : null,
        hour: d.getUTCHours(), wday: d.getUTCDay() });
    };
    backtestSeries(cs, hcs, m, tf, Object.assign({}, OPTS, { onEntry }));
  }
  return out;
}
const SESSION = h => h < 8 ? 'Asia (0–8 UTC)' : h < 13 ? 'London (8–13 UTC)' : h < 21 ? 'New York (13–21 UTC)' : 'Late (21–24 UTC)';
const WDAY = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
function group(tr, f, order) { const m = {}; for (const t of tr) { const k = f(t); if (k == null) continue; (m[k] = m[k] || []).push(t); }
  return (order || Object.keys(m)).filter(k => m[k]).map(k => Object.assign({ k }, btStat(m[k]))); }
function report(trades, meta) {
  trades.sort((a, b) => a.t0 - b.t0);
  const mid = trades.length ? trades[Math.floor(trades.length / 2)].t0 : 0;
  const yes = t => t.confirmed ? 'Confirmed' : 'Not confirmed', agree = t => t.d4h === t.dir && t.d1d === t.dir ? '4H and 1D agree' : t.d4h === t.dir || t.d1d === t.dir ? 'One agrees' : 'Neither agrees';
  const odds = {};
  for (const t of trades) { const k = oddsKey(t.tf, t.dir, t.conf, t.confirmed); (odds[k] = odds[k] || []).push(t); }
  for (const k in odds) odds[k] = btStat(odds[k]);
  return Object.assign(meta, {
    v: 1, updated: Math.floor(Date.now() / 1000), plan: OPTS.plan, fee: OPTS.fee, slip: OPTS.slip, maxHold: OPTS.maxHold, minN: BT_MIN_N,
    from: trades.length ? trades[0].t0 : null, to: trades.length ? trades[trades.length - 1].t0 : null,
    overall: btStat(trades),
    groups: {
      confirmed: group(trades, yes, ['Confirmed', 'Not confirmed']),
      tf: group(trades, t => TF_LABEL[t.tf], TFS_RUN.map(t => TF_LABEL[t])),
      side: group(trades, t => t.dir > 0 ? 'Long' : 'Short', ['Long', 'Short']),
      agreement: group(trades, t => 'Agreement ' + confBand(t.conf), ['Agreement 70+', 'Agreement 50-69', 'Agreement <50']),
      bigger: group(trades, agree, ['4H and 1D agree', 'One agrees', 'Neither agrees']),
      range: group(trades, t => t.range == null ? null : t.range < 0.1 ? '24h range under 10%' : t.range < 0.25 ? '24h range 10–25%' : '24h range 25%+', ['24h range under 10%', '24h range 10–25%', '24h range 25%+']),
      adx: group(trades, t => t.adx == null ? null : t.adx >= 30 ? 'ADX 30+' : t.adx >= 22 ? 'ADX 22–30' : 'ADX under 22', ['ADX 30+', 'ADX 22–30', 'ADX under 22']),
      session: group(trades, t => SESSION(t.hour), ['Asia (0–8 UTC)', 'London (8–13 UTC)', 'New York (13–21 UTC)', 'Late (21–24 UTC)']),
      weekday: group(trades, t => WDAY[t.wday], ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
    },
    // walk-forward check: does the confirmed vs not-confirmed gap hold on the newer half of the data too?
    walk: { split: mid, older: group(trades.filter(t => t.t0 < mid), yes, ['Confirmed', 'Not confirmed']), newer: group(trades.filter(t => t.t0 >= mid), yes, ['Confirmed', 'Not confirmed']) },
    odds
  });
}
async function main() {
  const t0 = Date.now(), all = [], fails = [];
  let markets;
  if (DEMO) { state.pairs = demoPairs(); markets = state.pairs.filter(p => p.kind === 'perp').slice(0, 8); }
  else markets = await gateMarkets();
  for (const m of markets) {
    try {
      const c = {};
      for (const tf of ['15m', '1h', '4h', '1d']) { c[tf] = DEMO ? demoCandles(m, tf, LIMIT[tf]) : await gateCandles(m.sym, tf); if (!DEMO) await sleep(150); }
      all.push(...runMarket(m, c));
    } catch (e) { fails.push(m.sym + ': ' + String(e && e.message || e).slice(0, 80)); }
  }
  const rep = report(all, { source: DEMO ? 'sample data' : 'Gate USDT perpetuals', markets: markets.map(m => m.root), fails, secs: Math.round((Date.now() - t0) / 1000) });
  if (!DEMO && rep.overall.n < 50) throw new Error('too few trades (' + rep.overall.n + '); not publishing');
  fs.writeFileSync(OUT, JSON.stringify(rep));
  const c = rep.groups.confirmed;
  console.log('backtest: ' + rep.overall.n + ' trades on ' + markets.length + ' markets (' + fails.length + ' failed) in ' + rep.secs + 's; ' +
    c.map(g => g.k + ' ' + g.n + ' trades, ' + Math.round(g.reach * 100) + '% reached target 1').join('; '));
}
main().catch(e => { console.error('backtest failed: ' + (e && e.stack || e)); process.exit(1); });
`);
