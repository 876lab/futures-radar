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
  // 1D setups for the lab only (kept out of the main numbers so they stay comparable with earlier nights)
  if (c['1d'] && c['1d'].length >= SIM_WARM + 20) { const cs = c['1d'], close = t => t + 86400;
    backtestSeries(cs, null, m, '1d', Object.assign({}, OPTS, { onEntry: (t, x) => { const dirs = { '4h': null, '1d': null };
      const cf = confirmSetup({ dir: t.dir, tf: '1d', dirs: { '4h': t.dir, '1d': t.dir }, range: 0, vol: 1e12, delisting: false });
      DAY_TR.push({ m: m.root, t0: t.t0, r: +t.r.toFixed(3), confirmed: cf.ok }); } })); }
  for (const tf of TFS_RUN) {
    const cs = c[tf], hcs = c[HTF[tf]]; if (!cs || cs.length < SIM_WARM + 20) continue;
    const S = computeSeries(cs), step = TFS[tf];
    const divs = rsiDivergences(cs, S.r12, SIM_WARM);
    if (tf !== '15m') signalStats(cs, S, divs, tf);
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
      const fb = fibLevels(cs.slice(Math.max(0, i - FIB_LOOK - 60), i + 1), x.an.atr);   // only candles up to the signal
      const fib = !fb ? null : fb.dir !== t.dir ? 'Last move went the other way' : fb.breakout || fb.retr < 0 ? 'Breakout past the swing end' : 'Pullback ' + fibZone(fb.retr);
      // experiments: the same entry with other stops and targets (stop at least k × ATR; all closed at 1.5R or 1R)
      const R0 = x.rc.levels.R, sim = (R, o2) => { const v = simTrade(cs, i, { dir: t.dir, conf: t.conf, levels: { R } }, Object.assign({}, OPTS, o2 || {}));
        return v && !v.unfinished ? +v.r.toFixed(3) : null; };
      const lab = { s15: sim(Math.max(R0, 1.5 * A)), s20: sim(Math.max(R0, 2 * A)), s25: sim(Math.max(R0, 2.5 * A)), t15: sim(R0, { plan: 'tp1' }), t10: sim(R0, { plan: 'tp1', tp1x: 1 }),
        s20t15: sim(Math.max(R0, 2 * A), { plan: 'tp1' }), s20t10: sim(Math.max(R0, 2 * A), { plan: 'tp1', tp1x: 1 }),
        mk: +(t.r + 0.3 * t.cost).toFixed(3) };
      const le = limitEntry(cs, S, i, x.rc, A, { maxHold: OPTS.maxHold });
      lab.pb = le && !le.miss ? le.r : null; lab.pbMiss = !!(le && le.miss);
      lab.trail = runExit(cs, S, i + 1, cs[i + 1].open * (1 + t.dir * OPTS.slip), t.dir, cs[i + 1].open * (1 + t.dir * OPTS.slip) - t.dir * R0, { maxHold: OPTS.maxHold, trail: true });
      lab.h48 = sim(R0, { maxHold: 48 });   // entry as a limit (maker) order: 0.02% instead of 0.05% on the way in, exits still 0.05%
      const dv = divAt(divs, i, 20);
      const lt = lightFor(close);
      out.push({ light: lt, m: m.root, tf, dir: t.dir, conf: t.conf, t0: t.t0, r: +t.r.toFixed(3), reach: t.mfe >= 1.5, how: t.how, bars: t.bars, lab, div: dv ? (dv.dir === t.dir ? 'with' : 'against') : 'none',
        confirmed: cf.ok, d4h: dirs['4h'], d1d: dirs['1d'], range: range == null ? null : +range.toFixed(4), vol: Math.round(vol),
        adx: x.an.adx == null ? null : +x.an.adx.toFixed(1), score: x.an.score, htf: x.han ? (x.han.score >= 20 ? 1 : x.han.score <= -20 ? -1 : 0) : null,
        r6: r6 == null ? null : +r6.toFixed(1), pctB: up != null && up > lb ? +((price - lb) / (up - lb)).toFixed(3) : null,
        ext: e20 != null ? +((price - e20) / A).toFixed(2) : null, vRatio: va ? +(cs[i].volume / va).toFixed(2) : null,
        hour: d.getUTCHours(), wday: d.getUTCDay(), fib });
    };
    backtestSeries(cs, hcs, m, tf, Object.assign({}, OPTS, { onEntry }));
  }
  return out;
}
// Round 2 experiments (5 Nov 2026). runExit follows a trade from candle k0 (the entry candle, entry price already known)
// with the split plan: stop first if both are touched; after target 1, the stop goes to entry, or with trail=true follows
// Supertrend (the line as of the previous candle's close, never looser than entry). Fees: feeIn on entry, OPTS.fee out.
function runExit(cs, S, k0, entry, dir, stop, o) {
  const R = Math.abs(entry - stop), tp1 = entry + dir * 1.5 * R, tp2 = entry + dir * 3 * R, last = Math.min(cs.length - 1, k0 + o.maxHold - 1);
  let cur = stop, half = false, legs = [], out = null;
  for (let k = k0; k <= last; k++) {
    const b = cs[k];
    if (half && o.trail && k > k0 && S.st.dir[k - 1] === dir && S.st.line[k - 1] != null) cur = dir > 0 ? Math.max(cur, S.st.line[k - 1]) : Math.min(cur, S.st.line[k - 1]);
    const hitStop = dir > 0 ? b.low <= cur : b.high >= cur;
    if (hitStop) { legs.push([half ? 0.5 : 1, cur * (1 - dir * OPTS.slip)]); out = k; break; }
    if (!half && (dir > 0 ? b.high >= tp1 : b.low <= tp1)) { legs.push([0.5, tp1]); half = true; cur = entry; }
    if (half && (dir > 0 ? b.high >= tp2 : b.low <= tp2)) { legs.push([0.5, tp2]); out = k; break; }
  }
  if (out == null) { if (k0 + o.maxHold - 1 > cs.length - 1) return null; legs.push([half ? 0.5 : 1, cs[last].close * (1 - dir * OPTS.slip)]); out = last; }
  const ex = legs.reduce((a, [f, px]) => a + f * px, 0) / legs.reduce((a, [f]) => a + f, 0);
  const gross = legs.reduce((a, [f, px]) => a + f * (px - entry) * dir, 0) / R;
  return +(gross - ((o.feeIn != null ? o.feeIn : OPTS.fee) * entry + OPTS.fee * ex) / R).toFixed(3);
}
// pullback entry: a limit order at the far edge of the setup's entry zone, valid for 3 candles; missed = null. Stop unchanged.
function limitEntry(cs, S, i, rc, A, o) {
  const d = rc.dir, L = rc.levels, lim = d > 0 ? L.zone[0] : L.zone[1], px = Math.abs(lim - L.price) < 0.1 * A ? L.price - d * 0.5 * A : lim;
  if ((d > 0 ? px <= L.stop : px >= L.stop) || Math.abs(px - L.stop) < 0.3 * A) return { miss: true };
  for (let k = i + 1; k <= Math.min(cs.length - 1, i + 3); k++) {
    if (d > 0 ? cs[k].low <= px : cs[k].high >= px) { const r = runExit(cs, S, k, px, d, L.stop, Object.assign({ feeIn: 0.0002 }, o)); return r == null ? null : { r }; }
  }
  return { miss: true };
}
// do RSI divergences and Supertrend flips (the chart's B/S marks) on their own point the right way? From the candle where
// each is known: does price move 1 ATR its way before 1 ATR against within 30 candles (a candle touching both counts as
// against)? Baseline: the same test from every 7th candle in both directions.
const SIG = {}, DAY_TR = [];
function firstTouch(cs, c, dir, A) {
  const p = cs[c].close;
  for (let k = c + 1; k < Math.min(cs.length, c + 31); k++) { const b = cs[k], fav = dir > 0 ? b.high - p : p - b.low, adv = dir > 0 ? p - b.low : b.high - p;
    if (adv >= A) return 0; if (fav >= A) return 1; }
  return null;
}
function signalStats(cs, S, divs, tf) {
  const g = SIG[tf] = SIG[tf] || { div: [0, 0], flip: [0, 0], base: [0, 0] }, add = (key, v) => { if (v == null) return; g[key][0] += v; g[key][1]++; };
  for (const d of divs) { const A = S.at[d.at]; if (A > 0) add('div', firstTouch(cs, d.at, d.dir, A)); }
  for (let i = SIM_WARM; i < cs.length - 1; i++) { const a = S.st.dir[i - 1], b = S.st.dir[i], A = S.at[i]; if (!(A > 0)) continue;
    if (a != null && b != null && a !== b) add('flip', firstTouch(cs, i, b, A));
    if (i % 7 === 0) { add('base', firstTouch(cs, i, 1, A)); add('base', firstTouch(cs, i, -1, A)); } }
}
// market light (Bitcoin daily, last finished day; no Fear & Greed or cycle score here) for the regime filter
let LIGHT_T = [], LIGHT_K = [];
function setLight(btc) { if (!btc || btc.length < 200) return; const S = lightSeries(btc); for (let i = 120; i < btc.length; i++) { const l = lightAt(btc, S, i, {}); if (l) { LIGHT_T.push(btc[i].time + 86400); LIGHT_K.push(l.k); } } }
function lightFor(at) { let lo = 0, hi = LIGHT_T.length - 1, j = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (LIGHT_T[m] <= at) { j = m; lo = m + 1; } else hi = m - 1; } return j >= 0 ? LIGHT_K[j] : null; }
const LAB_EXITS = { base: "Today's stop and targets", s15: 'Stop at least 1.5 ATR away', s20: 'Stop at least 2 ATR away', s25: 'Stop at least 2.5 ATR away',
  mk: 'Lower fees: limit-order entry (0.02%)', pb: 'Pullback entry: limit order in the entry zone, 3 candles', trail: 'Trail the stop with Supertrend after target 1', h48: 'Close after 48 candles instead of 96', t15: 'Close it all at 1.5R (no target 2)', t10: 'Close it all at 1R', s20t15: 'Stop 2+ ATR, close all at 1.5R', s20t10: 'Stop 2+ ATR, close all at 1R' };
const LAB_FILTERS = [['All setups', t => true], ['Confirmed setups (what Setups shows)', t => t.confirmed], ['1H and 4H, confirmed', t => t.confirmed && t.tf !== '15m'],
  ['4H only, confirmed', t => t.confirmed && t.tf === '4h'], ['Confirmed, skip weekends', t => t.confirmed && t.wday !== 0 && t.wday !== 6],
  ['1H and 4H, confirmed, skip weekends', t => t.confirmed && t.tf !== '15m' && t.wday !== 0 && t.wday !== 6], ['4H only, confirmed, skip weekends', t => t.confirmed && t.tf === '4h' && t.wday !== 0 && t.wday !== 6],
  ['Confirmed, with the 1D trend', t => t.confirmed && t.d1d === t.dir], ['Confirmed, market light calm (amber)', t => t.confirmed && t.light === 'amber'],
  ['Confirmed, market light not stormy', t => t.confirmed && t.light && t.light !== 'purple'], ['Confirmed, skip weekends, with the 1D trend', t => t.confirmed && t.wday !== 0 && t.wday !== 6 && t.d1d === t.dir],
  ['Confirmed, agreement under 70', t => t.confirmed && t.conf < 70], ['Confirmed, price within 1 ATR of its 20-candle average', t => t.confirmed && t.ext != null && Math.abs(t.ext) <= 1],
  ['Confirmed, no recent divergence against it', t => t.confirmed && t.div !== 'against'], ['Confirmed shorts only', t => t.confirmed && t.dir < 0], ['Confirmed longs only', t => t.confirmed && t.dir > 0]];
function labReport(trades, mid) {
  const rows = [], st = (tr, key) => { const v = tr.map(t => key === 'base' ? t.r : t.lab[key]).filter(x => x != null); if (!v.length) return null;
    return { n: v.length, avgR: +(v.reduce((a, b) => a + b, 0) / v.length).toFixed(4), win: +(v.filter(x => x > 0).length / v.length).toFixed(4) }; };
  for (const [fk, f] of LAB_FILTERS) { const tr = trades.filter(f), older = tr.filter(t => t.t0 < mid), newer = tr.filter(t => t.t0 >= mid);
    for (const ek of Object.keys(LAB_EXITS)) { if (ek !== 'base' && !(ek === 'mk' || ek === 'pb' || (['trail', 'h48'].includes(ek) && fk === 'Confirmed, skip weekends') || ['All setups', 'Confirmed setups (what Setups shows)', '1H and 4H, confirmed', '4H only, confirmed'].includes(fk))) continue;
      const a = st(tr, ek), o = st(older, ek), w = st(newer, ek); if (!a) continue;
      rows.push({ f: fk, e: LAB_EXITS[ek], n: a.n, avgR: a.avgR, win: a.win, older: o && o.avgR, newer: w && w.avgR, nOld: o ? o.n : 0, nNew: w ? w.n : 0 }); } }
  const div = {}, flip = {}, base = {};
  for (const tf in SIG) { const g = SIG[tf], r = x => x[1] ? { n: x[1], turn: +(x[0] / x[1]).toFixed(4) } : null; div[tf] = r(g.div); flip[tf] = r(g.flip); base[tf] = r(g.base); }
  const conf = trades.filter(t => t.confirmed), pbFill = conf.length ? +(conf.filter(t => t.lab.pb != null).length / conf.length).toFixed(4) : null;
  const D = DAY_TR.filter(t => t.confirmed).sort((a, b) => a.t0 - b.t0), day = D.length ? { n: D.length, avgR: +(D.reduce((a, t) => a + t.r, 0) / D.length).toFixed(4), win: +(D.filter(t => t.r > 0).length / D.length).toFixed(4),
    older: null, newer: null } : null;
  if (day) { const md = D[Math.floor(D.length / 2)].t0, a = D.filter(t => t.t0 < md), b = D.filter(t => t.t0 >= md), av = x => x.length ? +(x.reduce((s, t) => s + t.r, 0) / x.length).toFixed(4) : null;
    day.older = av(a); day.newer = av(b); rows.push({ f: '1D setups (separate run)', e: "Today's stop and targets", n: day.n, avgR: day.avgR, win: day.win, older: day.older, newer: day.newer, nOld: a.length, nNew: b.length }); }
  return { pbFill, rows, div, flip, base, divGroup: group(trades.filter(t => t.tf !== '15m'), t => ({ with: 'Divergence agrees', against: 'Divergence against', none: 'No recent divergence' })[t.div], ['Divergence agrees', 'No recent divergence', 'Divergence against']) };
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
      weekday: group(trades, t => WDAY[t.wday], ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']),
      fib: group(trades, t => t.fib, ['Breakout past the swing end', 'Pullback Under 23.6%', 'Pullback 23.6–38.2%', 'Pullback 38.2–50%', 'Pullback 50–61.8%',
        'Pullback 61.8–78.6%', 'Pullback 78.6–100%', 'Pullback Past 100%', 'Last move went the other way'])
    },
    // walk-forward check: does the confirmed vs not-confirmed gap hold on the newer half of the data too?
    lab: labReport(trades, mid),
    walk: { split: mid, older: group(trades.filter(t => t.t0 < mid), yes, ['Confirmed', 'Not confirmed']), newer: group(trades.filter(t => t.t0 >= mid), yes, ['Confirmed', 'Not confirmed']) },
    odds
  });
}
async function main() {
  const t0 = Date.now(), all = [], fails = [];
  let markets;
  if (DEMO) { state.pairs = demoPairs(); markets = state.pairs.filter(p => p.kind === 'perp').slice(0, 8); }
  else markets = await gateMarkets();
  try { const btc = markets.find(m => m.root === 'BTC'); if (btc) setLight(DEMO ? demoCandles(btc, '1d', LIMIT['1d']) : await gateCandles(btc.sym, '1d')); } catch (e) { fails.push('BTC light: ' + String(e && e.message || e).slice(0, 60)); }
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
  const L = rep.lab, best = [...L.rows].filter(r => r.n >= 200 && r.older != null && r.newer != null).sort((a, b) => Math.min(b.older, b.newer) - Math.min(a.older, a.newer)).slice(0, 6);
  console.log('lab (best on both halves): ' + best.map(r => r.f + ' + ' + r.e + ': n ' + r.n + ', avg ' + r.avgR + 'R (older ' + r.older + ', newer ' + r.newer + ')').join(' | '));
  console.log('lab round 2: pullback fill rate ' + L.pbFill + '; ' + L.rows.filter(r => /Pullback|Trail|48 candles|1D|light|1D trend/.test(r.e + r.f)).map(r => r.f + ' + ' + r.e + ': n ' + r.n + ', ' + r.avgR + 'R (' + r.older + ' / ' + r.newer + ')').join(' | '));
  console.log('lab signals: ' + Object.keys(L.div).map(tf => tf + ' div ' + JSON.stringify(L.div[tf]) + ' flip ' + JSON.stringify(L.flip[tf]) + ' base ' + JSON.stringify(L.base[tf])).join(' | '));
  console.log('lab divergence at entry: ' + L.divGroup.map(g => g.k + ' ' + g.n + ' avg ' + g.avgR.toFixed(3) + 'R').join(', '));
}
main().catch(e => { console.error('backtest failed: ' + (e && e.stack || e)); process.exit(1); });
`);
