// Engine tests: no look-ahead, trade rules, and a backtest stress run on sample data.
// The app's code is sliced by its section comments, so keep these markers in index.html:
//   "const DAY", "/* ---------- network", "/* ---------- sample data", "/* ---------- loading",
//   "/* ---------- indicators", "/* ---------- charts"
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const cut = (a, b) => { const i = src.indexOf(a), j = src.indexOf(b); if (i < 0 || j < 0 || j < i) throw new Error('marker missing: ' + (i < 0 ? a : b)); return src.slice(i, j); };
global.location = { hostname: '876lab.github.io', pathname: '/futures-radar/' };
let code = cut('const DAY', '/* ---------- network').replace(/const LS=.*\n/, 'const LS={get:(k,d)=>d,set(){}};\n');
code += cut('/* ---------- sample data', '/* ---------- loading') + cut('/* ---------- indicators', '/* ---------- charts');
code += `
let pass=0,fail=0;const ok=(c,m)=>{if(c)pass++;else{fail++;console.log('FAIL:',m)}};
// 1. no look-ahead: a signal at a past candle must equal a fresh calculation on candles up to that point
state.pairs=demoPairs();state.mode='demo';buildGroups();
for(const p of state.pairs.slice(0,8))for(const tf of ['15m','1h']){
  const cs=demoCandles(p,tf,700),S=computeSeries(cs);
  for(let t=0;t<12;t++){const L=60+Math.floor(Math.random()*(cs.length-61));
    const a=analyzeAt(cs,S,L),b=analyze(cs.slice(0,L+1)),ra=recommend(a,cs,null,tf),rb=recommend(b,cs.slice(0,L+1),null,tf);
    ok(JSON.stringify([a.score,a.support,a.resist,ra.rec,ra.conf,ra.levels&&ra.levels.stop])===JSON.stringify([b.score,b.support,b.resist,rb.rec,rb.conf,rb.levels&&rb.levels.stop]),'look-ahead mismatch '+p.id+' '+tf+' L='+L)}}
// 2. trade rules
const C=(o,h,l,c)=>({time:0,open:o,high:h,low:l,close:c,volume:1}),base={plan:'tp1',fee:0,slip:0,maxHold:50},L1={dir:1,conf:60,levels:{R:1}},S1={dir:-1,conf:60,levels:{R:1}};
let t=simTrade([C(100,100,100,100),C(100,100.5,99.5,100.2),C(100.2,101.6,100,101.4),C(101,101,101,101)],0,L1,base);ok(t.how==='target'&&Math.abs(t.r-1.5)<1e-9,'long target 1');
t=simTrade([C(100,100,100,100),C(100,101.6,98.9,100),C(100,100,100,100)],0,L1,base);ok(t.how==='stop'&&Math.abs(t.r+1)<1e-9,'stop first when both touched');
t=simTrade([C(100,100,100,100),C(100,100.5,99,99.2),C(99,99,96.9,97),C(97,97,97,97)],0,S1,{...base,plan:'tp2'});ok(t.how==='target'&&Math.abs(t.r-3)<1e-9,'short target 2');
t=simTrade([C(100,100,100,100),C(100,101.6,99.5,101),C(101,101,99.9,100),C(100,100,100,100)],0,L1,{...base,plan:'split'});ok(t.how==='breakeven'&&Math.abs(t.r-0.75)<1e-9,'split then breakeven');
t=simTrade([C(100,100,100,100),C(100,101.6,99.5,101),C(101,103.1,100.5,103),C(103,103,103,103)],0,L1,{...base,plan:'split'});ok(Math.abs(t.r-2.25)<1e-9,'split both targets');
t=simTrade([C(100,100,100,100),C(100,101.6,99.5,101),C(101,101,101,101)],0,L1,{...base,fee:0.001});ok(Math.abs(t.r-(1.5-0.2015))<1e-9,'fees');
const flat=[C(100,100,100,100)];for(let k=0;k<10;k++)flat.push(C(100,100.4,99.6,100.3));
t=simTrade(flat,0,L1,{...base,maxHold:5});ok(t.how==='time'&&t.exitIdx===5,'time exit');
t=simTrade(flat,5,L1,{...base,maxHold:50});ok(t.unfinished===true,'unfinished trade not counted');
// 3. stress run: every trade valid, no overlapping trades per market
const o={plan:'split',minConf:0,fee:0.0005,slip:0.0002,risk:2,maxHold:96};let n=0;const t0=Date.now();
for(const g of state.groups.filter(g=>g.kind==='perp').slice(0,12))for(const tf of ['15m','1h','4h']){
  const cs=demoCandles(g.primary,tf,1000),h=HTF[tf]?demoCandles(g.primary,HTF[tf],1000):null,tr=backtestSeries(cs,h,g.primary,tf,o);n+=tr.length;
  tr.forEach((x,k)=>{ok(x.exitIdx>x.i&&isFinite(x.r)&&x.t1>=x.t0,'invalid trade');if(k)ok(x.i>=tr[k-1].exitIdx,'overlapping trades')})}
// 4. max-loss guard (position sizing)
let z=sizeTrade(1000,2,0.02,0);ok(Math.abs(z.loss-20)<1e-9&&Math.abs(z.size-1000)<1e-9&&!z.over,'sizing without cap');
z=sizeTrade(1000,2,0.02,25);ok(!z.over,'under cap is not flagged');
z=sizeTrade(1000,2,0.02,20);ok(!z.over,'exactly at cap is not flagged');
z=sizeTrade(5000,10,0.01,200);ok(z.over&&Math.abs(z.loss-500)<1e-9&&Math.abs(z.fitSize-20000)<1e-6&&Math.abs(z.fitRisk-4)<1e-9&&Math.abs(z.fitSize*0.01-200)<1e-9,'over cap: size that fits loses exactly the cap');
z=sizeTrade(300,50,0.05,100);ok(z.over&&Math.abs(z.fitLev-100/0.05/300)<1e-9,'fit leverage');
const st=simStats([],2);ok(st.n===0,'empty stats');
ok(n>50,'backtest produced too few trades: '+n);
console.log('engine tests: '+pass+' passed, '+fail+' failed ('+n+' simulated trades in '+(Date.now()-t0)+' ms)');
if(fail)process.exit(1);
`;
eval(code);
