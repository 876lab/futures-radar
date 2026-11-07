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
    ok(JSON.stringify([a.score,a.support,a.resist,ra.rec,ra.conf,ra.levels&&ra.levels.stop])===JSON.stringify([b.score,b.support,b.resist,rb.rec,rb.conf,rb.levels&&rb.levels.stop]),'look-ahead mismatch '+p.id+' '+tf+' L='+L);
    // neutral wording: the reading describes the chart, never tells the user what to do (labels only; rules unchanged)
    ok(({long:'Long setup',short:'Short setup',hold:'Wait',avoid:'No setup'})[ra.rec]===ra.headline,'neutral headline for '+ra.rec+': '+ra.headline);
    ok(!/\b(buy|sell|you should|hold\.|take profit)\b/i.test(ra.text),'imperative wording in reading text: '+ra.text)}}
// delisting dates from the exchanges' market lists
{const now=Date.UTC(2026,9,23),D=864e5,di=delistInfo;
ok(di('binance',{contractType:'PERPETUAL',deliveryDate:4133404800000},now)===null,'binance: 2100 placeholder is not a delisting');
ok(di('binance',{contractType:'PERPETUAL',deliveryDate:now+5*D},now).at===now+5*D,'binance: perpetual deliveryDate before 2100 is the delisting time');
ok(di('binance',{contractType:'CURRENT_QUARTER',deliveryDate:now+5*D},now)===null,'binance: quarterly expiry is not a delisting');
ok(di('binance',{contractType:'PERPETUAL',deliveryDate:now-D},now)===null,'binance: past date ignored');
ok(di('bybit',{contractType:'LinearPerpetual',deliveryTime:'0'},now)===null,'bybit: 0 means no delisting');
ok(di('bybit',{contractType:'LinearPerpetual',deliveryTime:String(now+3*D)},now).at===now+3*D,'bybit: perpetual deliveryTime is the delisting time');
ok(di('bybit',{contractType:'LinearFutures',deliveryTime:String(now+3*D)},now)===null,'bybit: dated futures delivery is not a delisting');
let g=di('gate',{delisting_time:(now+2*D)/1000,delisted_time:(now+3*D)/1000},now);ok(g&&g.at===now+3*D&&g.ro===now+2*D,'gate: delisted_time with reduce-only from delisting_time');
g=di('gate',{delisting_time:0,delisted_time:0},now);ok(g===null,'gate: zero times mean no delisting');
g=di('gate',{delisting_time:(now+2*D)/1000},now);ok(g&&g.at===now+2*D&&g.ro===null,'gate: only reduce-only time known');
ok(di('gate',{delisted_time:'junk'},now)===null&&di('binance',null,now)===null&&di('bybit',{deliveryTime:now+3000*D},now)===null,'junk, missing and far-future values ignored');}
// confirmation rule (owner's choice 24 Oct 2026): at least one of 4H/1D agrees and no delisting; liquidity and range are context
{const base={dir:1,tf:'15m',dirs:{'4h':1,'1d':1},range:0.08,vol:50e6,delisting:false};
let c=confirmSetup(base);ok(c.ok&&!c.pending,'confirm: both agree');
c=confirmSetup({...base,dirs:{'4h':1,'1d':-1}});ok(c.ok,'confirm: one agreeing is enough');
c=confirmSetup({...base,dirs:{'4h':-1,'1d':0}});ok(!c.ok&&!c.pending&&c.why==='bigger','confirm: neither agrees fails');
c=confirmSetup({...base,dir:-1,dirs:{'4h':1,'1d':-1}});ok(c.ok,'confirm: short with 1D down');
c=confirmSetup({...base,delisting:true});ok(!c.ok&&c.why==='delisting','confirm: delisting fails');
c=confirmSetup({...base,vol:750e3,range:0.42});ok(c.ok&&c.checks.filter(x=>x.state==='mid').length===2,'confirm: liquidity and range are context only');
c=confirmSetup({...base,dirs:{}});ok(!c.ok&&c.pending,'confirm: nothing loaded is pending');
c=confirmSetup({...base,dirs:{'4h':-1}});ok(!c.ok&&c.pending,'confirm: one disagreeing and one missing is pending');
c=confirmSetup({...base,dirs:{'1d':1}});ok(c.ok&&!c.pending,'confirm: one agreeing is enough even if the other is missing');
// EPIC on 23 Oct 2026: 15m long, 4H and 1D down, delisting announced
c=confirmSetup({dir:1,tf:'15m',dirs:{'4h':-1,'1d':-1},range:0.4253,vol:758e3,delisting:true});ok(!c.ok,'confirm: EPIC example not confirmed');
ok(Math.abs(range24([{time:0,high:2,low:1},{time:86400,high:1.2,low:1.1},{time:90000,high:1.3,low:1.0}])-0.3)<1e-9,'range24 uses only the last 24 hours');
ok(range24([])===null&&range24(null)===null,'range24 empty');
ok(JSON.stringify(delistTickers('Delisting of 1000PEPEUSDT and EPICUSDT Perpetual Contracts'))==='["PEPE","EPIC"]','delistTickers: contract names');
ok(JSON.stringify(delistTickers('Bybit Will Delist the EPIC/USDT Spot Trading Pair'))==='["EPIC"]','delistTickers: spot pair');
ok(delistTickers('New listing: EPICUSDT').length===0,'delistTickers: needs the word delist');}
// nightly backtest helpers
{const [lo,hi]=wilson(58,100);ok(Math.abs(lo-0.4821)<0.001&&Math.abs(hi-0.6719)<0.001,'wilson 58/100');
ok(wilson(0,0)[0]===0&&wilson(0,0)[1]===0,'wilson with no trades');
const s=btStat([{reach:true,r:1.2},{reach:false,r:-1},{reach:true,r:0.5},{reach:false,r:0.1}]);ok(s.n===4&&s.reach===0.5&&s.win===0.75&&Math.abs(s.avgR-0.2)<1e-9&&s.lo<0.5&&s.hi>0.5,'btStat');
ok(btStat([]).n===0,'btStat empty');
// company filings: tickers cleaned, links go to sec.gov EDGAR
ok(cleanTicker(' $sofi ')==='SOFI'&&cleanTicker('BRK.B')==='BRK.B'&&cleanTicker('<x>')===null&&cleanTicker('TOOLONGX')===null&&cleanTicker('')===null,'filings: ticker cleaning');
ok(cleanFilList(['googl','GOOGL','<b>',7,'sofi']).join()==='GOOGL,SOFI'&&cleanFilList('x').length===0,'filings: saved list cleaned');
ok(edgarURL('SOFI','10-Q')==='https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=SOFI&type=10-Q&dateb=&owner=include&count=40'&&!edgarURL('GOOGL','').includes('type='),'filings: EDGAR links');
// weekly / monthly candles (Gate builds them from daily ones) and the market light
{const D=86400,mon=Date.UTC(2026,9,26)/1000;
ok(barStart('1w',Date.UTC(2026,9,29,15)/1000)===mon&&barStart('1w',mon)===mon&&barStart('1w',mon-1)===mon-7*D,'barStart: weeks start Monday 00:00 UTC');
ok(barStart('1M',Date.UTC(2026,9,31,23)/1000)===Date.UTC(2026,9,1)/1000&&barStart('1M',Date.UTC(2026,10,1)/1000)===Date.UTC(2026,10,1)/1000&&barStart('1h',7300)===7200,'barStart: months start on the 1st; others unchanged');
const day=Array.from({length:10},(_,i)=>({time:Date.UTC(2026,9,23)/1000+i*D,open:100+i,high:105+i,low:95+i,close:101+i,volume:10}));
const w=aggCandles(day,'1w');ok(w.length===2&&w[0].time===mon-7*D&&w[0].open===100&&w[0].close===103&&w[0].high===107&&w[0].low===95&&w[0].volume===30&&w[1].time===mon&&w[1].open===103&&w[1].close===110&&w[1].volume===70,'aggCandles: Fri-Sun then a full week');
const m=aggCandles(day,'1M');ok(m.length===2&&m[0].close===109&&m[1].time===Date.UTC(2026,10,1)/1000&&m[1].open===109,'aggCandles: months split on the 1st');
ok(demoCandles(state.pairs[0],'1M',400).every((k,i,a)=>!i||k.time>a[i-1].time),'demo monthly candles are in order');
let seed=7;const rnd=()=>{seed=(seed*16807)%2147483647;return seed/2147483647};
const mk=steps=>{let p=100,t=Date.UTC(2025,0,1)/1000;return steps.map(r=>{const o=p;p=p*(1+r);const k={time:t,open:o,high:Math.max(o,p)*1.004,low:Math.min(o,p)*0.996,close:p,volume:1};t+=D;return k})};
const calm=Array.from({length:300},()=>(rnd()-0.5)*0.02);
const rally=mk([...calm,...Array.from({length:30},()=>0.016)]),crash=mk([...calm,...Array.from({length:12},()=>-0.03)]),
  storm=mk([...calm,...Array.from({length:20},(_,i)=>i%2?0.07:-0.065)]),flat=mk([...calm,...Array.from({length:20},()=>(rnd()-0.5)*0.01)]);
const at=(cs,ext)=>lightAt(cs,lightSeries(cs),cs.length-1,ext);
const a=at(rally,{fng:80,cycle:50}),b=at(crash,{fng:10,cycle:25}),c=at(storm,{fng:50,cycle:50}),f=at(flat,{fng:50,cycle:50});
ok(a&&a.k==='red'&&a.hot>=3,'light: fast rally with greed is red ('+(a&&a.k+' '+a.hot+'/'+a.cold)+')');
ok(b&&b.k==='green'&&b.cold>=3&&b.why.includes('dd'),'light: hard fall with fear is green ('+(b&&b.k+' '+b.hot+'/'+b.cold)+')');
ok(c&&c.k==='purple'&&c.storm&&c.hot<3&&c.cold<3,'light: big swings without an extreme are purple ('+(c&&c.k+' '+c.volPct)+')');
ok(f&&f.k==='amber'&&!f.storm,'light: calm sideways is amber ('+(f&&f.k+' '+f.volPct)+')');
ok(at(crash,{})&&at(crash,{}).fng===null&&lightAt(crash.slice(0,100),lightSeries(crash.slice(0,100)),99)===null,'light: works without Fear & Greed; needs 120+ days');
const S=lightSeries(storm);let same=true;for(const i of [150,200,250,300,315]){const x=lightAt(storm,S,i,{cycle:40}),y=lightAt(storm.slice(0,i+1),lightSeries(storm.slice(0,i+1)),i,{cycle:40});if(JSON.stringify(x)!==JSON.stringify(y))same=false}
ok(same,'light: no look-ahead (same reading on data cut at that day)');
const h=lightHistory(storm,null),tot=Object.values(h).reduce((s,x)=>s+x.days,0);
ok(tot===storm.length-120&&Object.values(h).every(x=>x.eps>=1&&x.eps<=x.days&&(!x.f30||x.f30.up>=0&&x.f30.up<=1)),'light history: every day counted once, sane stats ('+tot+')');}
// support and resistance zones from swing points (information only)
{const bar=(t,h,l)=>({time:t*3600,open:(h+l)/2,high:h,low:l,close:(h+l)/2,volume:1});
// price bounces between ~90 (floor) and ~110 (ceiling) three times, then sits at 100
const path=[];for(let r=0;r<3;r++){for(let i=0;i<10;i++)path.push(90+i*2);for(let i=0;i<10;i++)path.push(110-i*2)}for(let i=0;i<10;i++)path.push(100);
const cs=path.map((m,i)=>bar(i,m+1,m-1));
const P=pivots(cs,5,0);ok(P.hi.length>=3&&P.lo.length>=2&&P.hi.every(x=>Math.abs(x.p-111)<1e-9),'pivots: swing highs at the ceiling ('+P.hi.length+' highs, '+P.lo.length+' lows)');
const r=srLevels(cs,2);
ok(r&&r.res.length===1&&Math.abs(r.res[0].p-111)<1e-9&&r.res[0].tests===3&&r.sup.length===2&&r.sup.some(z=>Math.abs(z.p-89)<0.01&&z.tests>=2)&&Math.abs(r.sup[0].p-91)<0.01,'sr: ceiling is resistance tested 3 times, floor is support ('+JSON.stringify(r&&[r.res.map(z=>[z.p,z.tests]),r.sup.map(z=>[z.p,z.tests])])+')');
ok(r.res[0].dist>0&&r.sup.every(z=>z.dist<0&&!z.flip)&&!r.at,'sr: distances, nearest first, no flip on a plain floor');
// break above the ceiling: old resistance (111) becomes support marked as a flip
const up=[...path,...[104,108,112,116,120,124,126,122,118,116,118,120,122,124,123,122].map(x=>x)],cs2=up.map((m,i)=>bar(i,m+1,m-1)),r2=srLevels(cs2,2);
const old=r2&&r2.sup.find(z=>Math.abs(z.p-111)<1);ok(old&&old.flip,'sr: broken resistance listed as support that was resistance');
// price sitting inside a zone is "being tested"
const cs3=[...cs,bar(60,111.4,110.6)],r3=srLevels(cs3,2);ok(r3&&r3.at&&Math.abs(r3.at.p-111)<1e-9,'sr: price at the ceiling is testing it');
ok(srLevels(cs.slice(0,12),2)===null&&srLevels(cs,0)===null,'sr: needs enough candles and an ATR');
// no look-ahead: levels at a past candle equal levels computed on candles cut there
let conf=true;for(const L of [25,30,40,50,61]){const q=pivots(cs2.slice(0,L+1),5,0);if([...q.hi,...q.lo].some(x=>x.i>L-5))conf=false}
ok(conf,'sr: a turning point counts only after 5 later candles confirm it');}
// price alerts (kept on the device)
{const t0=Date.UTC(2026,10,3,12);
const up=newAlert('INTC','INTC',40,36.5,t0),dn=newAlert('BTC','BTC',60000,78000,t0);
ok(up.d===1&&dn.d===-1&&up.hit===null&&newAlert('X','X',10,10,t0)===null&&newAlert('X','X',0,10,t0)===null&&newAlert('X','X',5,0,t0)===null,'alerts: direction from price now; no alert at the current price, zero or no price');
ok(!alertHit(up,39.99)&&alertHit(up,40)&&alertHit(up,41)&&!alertHit(dn,60000.01)&&alertHit(dn,59000),'alerts: rings at or past the price in its direction');
ok(!alertHit(Object.assign({},up,{hit:t0}),45),'alerts: a reached alert does not ring again');
const H=3600,cs=[{time:t0/1000-H,high:41,low:35},{time:t0/1000,high:39,low:36},{time:t0/1000+H,high:40.2,low:38},{time:t0/1000+2*H,high:42,low:39}];
const hit=alertTouched(up,cs);ok(hit&&hit.at===t0+H*1000,'alerts: closed-app check ignores candles before the alert, finds the first after');
ok(alertTouched(newAlert('INTC','INTC',30,36.5,t0),cs)===null&&alertTouched(Object.assign({},up,{hit:1}),cs)===null,'alerts: nothing touched, or already reached');
const many=Array.from({length:70},(_,i)=>newAlert('M'+i,'M',10+i,5,t0));
const cl=cleanAlerts([up,up,dn,null,'x',{k:'<b>',p:-1,d:1,t:1},{k:'A',p:5,d:2,t:1},{k:'A',p:5,d:1,t:'1'},{...up,p:41,id:'bad id <x>'}]);
ok(cl.length===3&&cl[0].id===up.id&&cl[2].id!==up.id&&!cl[2].id.includes('<')&&cleanAlerts(many).length===AL_MAX&&cleanAlerts('x').length===0,'alerts: saved list cleaned, duplicates dropped, capped at '+AL_MAX+' ('+cl.length+')');}
// price alerts: far-away prices and typo suggestions (owner typed $132.90 for ZEC at $1,133)
ok(alertFar(132.9,1133.5)&&!alertFar(40,36.5)&&!alertFar(74900,76706)&&!alertFar(0,10),'alerts: far from price (over 25%) is flagged');
ok(alertTypo(132.9,1133.5)[0]===1132.9&&alertTypo(7490,76706).join()==='77490,74900'&&alertTypo(767060,76806)[0]===76706&&alertTypo(1.85,0.1855)[0]===0.185&&alertTypo(11133.5,1135)[0]===1133.5&&!alertTypo(11335,1133.5).length,'alerts: typo suggestions (missing digit, extra digit, decimal point)');
ok(!alertTypo(40,36.5).length&&!alertTypo(5,36.5).length&&!alertTypo(0,1).length,'alerts: no suggestion when nothing lands near the price');
// company profiles for stock futures and US market hours
{const miss=[...STOCKS].filter(t=>!CO[t]||!CO_EX[CO[t][0]]||typeof CO[t][1]!=='string');
ok(!miss.length,'company profiles: every stock has an exchange and description (missing: '+miss.join(' ')+')');
ok(Object.values(CO).every(c=>c[1].length>=30&&c[1].length<=260&&!/\b(buy|sell|undervalued|cheap|should)\b/i.test(c[1])),'company profiles: short, factual wording');
ok(CO.WMT[0]==='N'&&CO.SHOP[0]==='N'&&CO.BMNR[0]==='Y'&&CO.INTC[0]==='N'&&CO.JPM[0]==='Y'&&CO.PLTR[0]==='N','company profiles: listings checked 4 Nov 2026');
const ny=(y,m,d,h,mi)=>Date.UTC(y,m,d,h+5,mi);   // November: New York is UTC-5
ok(usMarket(ny(2026,10,4,10,0)).open&&!usMarket(ny(2026,10,4,9,29)).open&&usMarket(ny(2026,10,4,9,30)).open&&!usMarket(ny(2026,10,4,16,0)).open,'US market hours: 9:30am to 4pm New York time');
ok(!usMarket(ny(2026,10,7,12,0)).open&&!usMarket(ny(2026,10,8,12,0)).open,'US market hours: closed at weekends');
ok(usMarket(Date.UTC(2026,6,1,13,45)).open&&!usMarket(Date.UTC(2026,6,1,20,30)).open,'US market hours follow New York summer time');}
// 200-week EMA lookup: own week on the 1W chart, last completed week elsewhere
{const W0=Date.UTC(2021,0,4)/1000,wk=Array.from({length:260},(_,i)=>({time:W0+i*604800,open:100+i,high:101+i,low:99+i,close:100+i,volume:1}));
ok(w200Series(wk.slice(0,199))===null,'200W EMA: needs 200 weeks');
const W=w200Series(wk),last=wk[259].time,e=ema(wk.map(k=>k.close),200);
ok(Math.abs(w200At(W,last,true)-e[259])<1e-9&&Math.abs(w200At(W,last+3*86400,false)-e[258])<1e-9&&Math.abs(w200At(W,last+3*86400+3600,false)-e[258])<1e-9,'200W EMA: 1W uses its own week, smaller candles use the last completed week');
ok(w200At(W,wk[199].time,false)===null&&w200At(W,wk[200].time+60,false)===e[199],'200W EMA: nothing before the first full 200 weeks');
ok(w200At(W,last+30*86400,false)===e[259],'200W EMA: after the last weekly candle, the latest value');}
// simulator in dollars (plain summary)
{const T=(r,cost,how,t0,t1)=>({r,cost,how,t0,t1});
const tr=[T(-1.05,0.05,'stop',0,3600),T(0.68,0.07,'breakeven',3600,7200),T(2.9,0.1,'target',7200,86400*3),T(0.04,0.06,'time',100,200),T(-1.04,0.04,'stop',300,400)];
const M=simMoney(tr,1000,2);
ok(M.risk===20&&M.n===5&&M.wins===2&&M.losses===2&&M.even===1,'sim money: $20 risk, 2 won, 2 lost, 1 even');
ok(Math.abs(M.net-(-1.05+0.68+2.9+0.04-1.04)*20)<1e-9&&Math.abs(M.fees-0.32*20)<1e-9&&Math.abs(M.beforeFees-M.net-M.fees)<1e-9&&Math.abs(M.end-1000-M.net)<1e-9,'sim money: net, fees and end balance');
ok(Math.abs(M.avgWin-(0.68+2.9)/2*20)<1e-9&&Math.abs(M.avgLoss-(-1.045*20))<1e-9&&M.how.stop===2&&Math.abs(M.days-3)<1e-9,'sim money: typical win and loss, exits, days covered');
ok(simMoney([],100,2).n===0&&simMoney([],100,2).net===0,'sim money: no trades');
ok(fmtDur(1800)==='30 min'&&fmtDur(3600)==='1 hour'&&fmtDur(5*3600)==='5 hours'&&fmtDur(30*3600)==='30 hours'&&fmtDur(3*86400)==='3 days','durations in words');}
// RSI divergence (information only): regular bearish/bullish divergence, known 3 candles after the second swing
{const H=3600,mk=(arr,rs)=>arr.map((m,i)=>({time:i*H,open:m,high:m+0.5,low:m-0.5,close:m,volume:1}));
// two rising price highs at i=10 and i=30, with RSI lower at the second: bearish
const prices=[],rsi=[];for(let i=0;i<45;i++){const peak1=10-Math.abs(i-10),peak2=12-Math.abs(i-30);const p=i<20?100+Math.max(0,peak1):100+Math.max(0,peak2);prices.push(p);rsi.push(i<20?50+Math.max(0,peak1)*2.5:50+Math.max(0,peak2)*1.2)}
const cs=mk(prices),d=rsiDivergences(cs,rsi,0);
ok(d.length===1&&d[0].dir===-1&&d[0].a.i===10&&d[0].b.i===30&&d[0].at===33,'divergence: higher high with lower RSI high is bearish, known 3 candles later ('+JSON.stringify(d.map(x=>[x.dir,x.a.i,x.b.i,x.at]))+')');
ok(divAt(d,32,20)===null&&divAt(d,33,20)===d[0]&&divAt(d,53,20)===d[0]&&divAt(d,54,20)===null,'divergence: only from its confirmation candle, for 20 candles');
const r2=rsi.map((v,i)=>i<20?v:50+(v-50)*3);ok(rsiDivergences(cs,r2,0).length===0,'divergence: no divergence when RSI confirms the new high');
const inv=mk(prices.map(p=>200-p)),rinv=rsi.map(v=>100-v);const d2=rsiDivergences(inv,rinv,0);ok(d2.length===1&&d2[0].dir===1,'divergence: lower low with higher RSI low is bullish');
let same=true;for(const L of [33,36,44]){const a=rsiDivergences(cs.slice(0,L+1),rsi.slice(0,L+1),0),b=d.filter(x=>x.at<=L);if(JSON.stringify(a)!==JSON.stringify(b))same=false}
ok(same,'divergence: no look-ahead (same result on data cut at each candle)');}
// backtest lab: picks must beat today's rules on both halves
{const base={f:'Confirmed setups (what Setups shows)',e:"Today's stop and targets",n:2000,avgR:-0.1,older:-0.05,newer:-0.15,nOld:1000,nNew:1000};
const a={f:'4H only, confirmed',e:'x',n:600,avgR:0.05,older:0.02,newer:0.08,nOld:300,nNew:300},b={f:'y',e:'x',n:600,avgR:0.2,older:0.5,newer:-0.2,nOld:300,nNew:300},c={f:'z',e:'x',n:90,avgR:0.5,older:0.5,newer:0.5,nOld:45,nNew:45};
const L=cleanLab({rows:[base,a,b,c,{f:'bad'}],div:{'1h':{n:10,turn:0.6},'15m':{n:1,turn:1}},flip:{},base:{},divGroup:[]});
const P=labPicks(L,200);ok(L.rows.length===4&&P.base&&P.picks.length===1&&P.picks[0].f==='4H only, confirmed'&&!L.div['15m'],'lab: only ideas better on both halves with enough trades are picked');
ok(cleanLab(null)===null&&cleanLab({rows:[]})===null,'lab: missing or empty');}
// hidden divergence and stop-hunts (information only)
{const H=3600,mk=arr=>arr.map((m,i)=>({time:i*H,open:m,high:m+0.5,low:m-0.5,close:m,volume:1}));
// uptrend pullbacks: lows at i=10 (100) and i=30 (103, a higher low) while RSI lows go 40 -> 34: hidden bullish
const pr=[],rs=[];for(let i=0;i<45;i++){const d1=Math.abs(i-10),d2=Math.abs(i-30);pr.push(i<20?100+Math.min(d1,10)*0.8:103+Math.min(d2,10)*0.8);rs.push(i<20?40+Math.min(d1,10)*2:34+Math.min(d2,10)*2.5)}
const cs=mk(pr),e50=pr.map(()=>95),d=rsiDivergences(cs,rs,0,e50),hd=d.filter(x=>x.kind==='hidden');
ok(hd.length===1&&hd[0].dir===1&&hd[0].a.i===10&&hd[0].b.i===30&&hd[0].at===33,'hidden divergence: higher low with lower RSI low in an uptrend ('+JSON.stringify(d.map(x=>[x.kind,x.dir,x.a.i,x.b.i]))+')');
ok(rsiDivergences(cs,rs,0,pr.map(()=>110)).filter(x=>x.kind==='hidden').length===0&&rsiDivergences(cs,rs,0).filter(x=>x.kind==='hidden').length===0,'hidden divergence: only with price above its 50-candle average (and only when it is passed)');
ok(divAt(d,40,20)===null&&divAt(d,40,20,'hidden')===hd[0],'divAt keeps regular and hidden apart');
// stop-hunt: swing high 110 at i=10, closes stay below it, then i=30 spikes to 111 and closes at 107
const c=[];for(let i=0;i<40;i++){const m=i===10?109:104+Math.sin(i)*1.5;c.push({time:i*H,open:m,high:i===10?110:m+0.6,low:m-0.6,close:m,volume:1})}
c[30]={time:30*H,open:106,high:111,low:105.5,close:107,volume:1};const atr=c.map(()=>2);
const h=stopHunts(c,atr,0),bear=h.filter(x=>x.dir<0);
ok(bear.length===1&&bear[0].i===30&&bear[0].level===110&&bear[0].j===10&&bear[0].ext===111,'stop-hunt: wick above a swing high that closes back below ('+JSON.stringify(h)+')');
const c2=c.map(k=>({...k}));c2[30]={...c2[30],close:110.5};ok(stopHunts(c2,atr,0).filter(x=>x.dir<0).length===0,'stop-hunt: a close above the high is a breakout, not a hunt');
const c3=c.map(k=>({...k}));c3[20]={...c3[20],close:110.2,high:110.4};{const h3=stopHunts(c3,atr,0).filter(x=>x.dir<0);ok(!h3.some(x=>x.level===110)&&h3.some(x=>x.level===110.4),'stop-hunt: a level already closed past is not reused (the newer swing high is)')}
const c4=c.map(k=>({...k}));c4[30]={...c4[30],high:110.2};ok(stopHunts(c4,atr,0).filter(x=>x.dir<0).length===0,'stop-hunt: needs a wick at least 0.15 ATR past the level');
let same=true;for(const L of [29,30,35]){const a=stopHunts(c.slice(0,L+1),atr.slice(0,L+1),0),b=h.filter(x=>x.at<=L);if(JSON.stringify(a)!==JSON.stringify(b))same=false}
ok(same,'stop-hunt: no look-ahead');}
// wave signals (1D, owner request 7 Nov 2026): WaveTrend maths, long-average fallback, rules, no look-ahead
{ok(waveLen(400)===200&&waveLen(220)===200&&waveLen(219)===100&&waveLen(120)===100&&waveLen(119)===50&&waveLen(70)===50&&waveLen(69)===0,'wave: long average 200 → 100 → 50 → none by history');
const flat=Array.from({length:80},(_,i)=>({time:i*86400,open:100,high:101,low:99,close:100})),wf=waveTrend(flat);
ok(wf.w1[79]!=null&&Math.abs(wf.w1[79])<1e-9&&Math.abs(wf.w2[79])<1e-9,'wave: flat prices give a zero wave');
const rise=Array.from({length:80},(_,i)=>({time:i*86400,open:100+i,high:101+i,low:99+i,close:100+i})),wr=waveTrend(rise);ok(wr.w1[79]>WAVE_OB,'wave: a steady rise reads overheated ('+wr.w1[79].toFixed(1)+')');
// a long rise, a slide back to the long average, then a sharp drop and bounce: a low-wave dot, and none while above the average
const cs=[];let p=100;for(let i=0;i<300;i++){p=i<200?p*1.004:i<285?p*0.994:i<290?p*0.97:p*1.02;cs.push({time:i*86400,open:p,high:p*1.01,low:p*0.99,close:p})}
const at=computeSeries(cs).at,W=waveSignals(cs,at,1),up=W.sig.filter(w=>w.dir>0);
ok(W.len===200&&up.length>=1&&up.every(w=>w.i>=285&&w.w<=WAVE_OS&&W.e20[w.i]<=W.eL[w.i]*1.01),'wave: low-wave dot after the drop, with the 20-day at the 200-day ('+JSON.stringify(up.map(w=>w.i))+')');
const hi=W.sig.filter(w=>w.dir<0);ok(hi.every(w=>cs[w.i].close>=W.eL[w.i]+3*at[w.i]&&w.w>=WAVE_OB),'wave: high-wave dots only when stretched 3 ATR above the average');
const sp=W.sig.filter(w=>w.dir>0).map(w=>w.i);ok(sp.every((v,k)=>!k||v-sp[k-1]>5),'wave: same-side dots at least 6 days apart');
const d=demoCandles(state.pairs[0],'1d',400),Sd=computeSeries(d),Wd=waveSignals(d,Sd.at,1);let same=true;
for(const L of [250,300,350,399]){const a=waveSignals(d.slice(0,L+1),Sd.at.slice(0,L+1),1).sig,b=Wd.sig.filter(w=>w.i<=L);if(JSON.stringify(a)!==JSON.stringify(b))same=false}
{const c5=[100,110,90,120,80].map((x,i)=>({time:i,close:x}));ok(Math.abs(holdReturn(c5,0,3)-0.2)<1e-12&&holdReturn(c5,2,3)===null,'wave hold: return after h days, none past the end');
const hs=holdStat([0.1,-0.2,0.3,0.05],1),hd=holdStat([0.1,-0.2,0.3,0.05],-1);ok(hs.n===4&&hs.pos===0.75&&Math.abs(hs.med-0.075)<1e-9&&hd.pos===0.25&&Math.abs(hd.med+0.075)<1e-9&&holdStat([],1)===null,'wave hold: share going the dot way and median, both directions');}
ok(same,'wave: no look-ahead ('+Wd.sig.length+' signals on sample data)');
ok(waveSignals(d.slice(0,60),Sd.at.slice(0,60),1).len===0&&waveSignals(d.slice(0,60),Sd.at.slice(0,60),1).sig.length===0,'wave: no dots without a long average');}
// public track record: cleaning and stats (losses and unscored records kept, junk dropped)
{const rec=(o)=>Object.assign({m:'BTC',tf:'1h',dir:1,conf:72,confirmed:true,t0:Date.UTC(2026,9,27)/1000,entry:100,stop:98,how:'stop',r:-1.02,reach:false,t1:Date.UTC(2026,9,27,5)/1000},o);
const raw={start:1,updated:2,source:'Gate',markets:['BTC'],open:[rec({how:undefined}),{m:'X'}],closed:[rec(),rec({how:'target',r:2.1,reach:true,dir:-1,stop:102,confirmed:false}),
  rec({how:'breakeven',r:0.68,reach:true,tf:'4h',t0:Date.UTC(2026,10,2)/1000}),rec({how:'nodata',r:null,t1:Date.UTC(2026,10,9)/1000}),rec({how:'win!'}),rec({r:'1'}),rec({tf:'15m'}),null,'x',rec({r:99})]};
const d=cleanTrack(raw);ok(d&&d.open.length===1&&d.closed.length===5,'track: junk records dropped ('+(d&&d.closed.length)+')');
ok(d.closed[4].r===5&&d.closed[3].how==='nodata'&&d.closed[3].r===null,'track: wild R capped, unscored record kept');
ok(cleanTrack({open:[]})===null&&cleanTrack('x')===null&&cleanTrack(null)===null,'track: not a track record');
const s=trackStats(d.closed.slice(0,4));ok(s.overall.n===3&&s.nodata===1&&Math.abs(s.overall.reach-2/3)<1e-9&&Math.abs(s.overall.avgR-(-1.02+2.1+0.68)/3)<1e-9,'track: stats leave out unscored records only');
ok(s.month.map(r=>r.k+':'+r.n).join()==='Nov 2026:1,Oct 2026:2','track: by month, newest first');
// CSV download of finished records (RFC 4180 quoting; formula-looking text neutralised; numbers and unscored rows kept)
{const csv=trackCSV(d.closed.slice(0,4)),L=csv.split('\\r\\n');
ok(L.length===6&&L[5]===''&&L[0]===TR_CSV_HEAD.join(','),'track csv: header, one line per record, CRLF ('+L.length+')');
ok(L[1]==='BTC,1H,long,72,yes,2026-10-27T00:00:00Z,100,98,,,2026-10-27T05:00:00Z,stop,-1.02,no,','track csv: first row, oldest first ('+L[1]+')');
ok(L[3].startsWith('BTC,1H,long')&&L[3].endsWith(',no price data,,,')&&L[4].includes(',4H,'),'track csv: unscored record kept with empty result');
const c2=cleanTrack({open:[],closed:[rec({m:'=HYPERLINK("x")',tp1:103,tp2:106,exit:103.5,how:'target',r:2.4,reach:true})]}),L2=trackCSV(c2.closed).split('\\r\\n');
ok(L2[1].startsWith('"'+"'"+'=HYPERLINK(""x"")",')&&L2[1].endsWith(',103,106,2026-10-27T05:00:00Z,target 2,2.4,yes,103.5'),'track csv: formula guard, quotes doubled, targets and exit ('+L2[1]+')');
ok(csvCell(-1.5)==='-1.5'&&csvCell('-x')==="'"+'-x'&&csvCell('a,b')==='"a,b"'&&csvCell(null)===''&&csvCell(NaN)==='','track csv: cells');}
ok(s.side.map(r=>r.k+r.n).join()==='Long2,Short1'&&s.tf.map(r=>r.k+r.n).join()==='1H2,4H1'&&s.confirmed[1].n===1,'track: by side, candle size, confirmed');
ok(s.latest.length===4&&s.latest[0].how==='nodata'&&s.latest.some(r=>r.r<0),'track: latest list keeps losses and unscored records');}
// live track record beside the past win rate: narrowest group with enough finished setups
{const mk=(n,o)=>Array.from({length:n},(_,i)=>Object.assign({m:'BTC',tf:'1h',dir:-1,confirmed:true,t0:i,t1:i+1,how:i%3?'stop':'breakeven',r:i%3?-1:0.7,reach:!(i%3)},o));
const cl=[...mk(120),...mk(60,{dir:1}),...mk(50,{dir:1,confirmed:false}),...mk(40,{tf:'4h'}),...mk(30,{how:'nodata',r:null,reach:false})];
const a=trackLike(cl,'1h',-1,true,100);ok(a.exact&&a.st.n===120&&a.label==='confirmed 1H short setups'&&Math.abs(a.st.reach-40/120)<1e-9,'track like: exact group when it has enough ('+(a.st&&a.st.n)+')');
const b=trackLike(cl,'1h',1,true,100);ok(!b.exact&&b.st.n===180&&b.label==='confirmed 1H setups','track like: falls back to same size and confirmation');
const c=trackLike(cl,'1h',1,false,100);ok(c.st.n===230&&c.label==='all 1H setups','track like: then same candle size');
const e=trackLike(cl,'4h',-1,true,100);ok(e.st.n===270&&e.label==='all 1H and 4H setups'&&e.all===270,'track like: then everything, unscored left out');
ok(trackLike(cl,'4h',-1,true,500).st===null&&trackLike(cl,'15m',1,true,100)===null,'track like: nothing under the minimum, no 15m');}
// crypto cycle gauge (information only)
{const D=86400,mk=(n,f)=>Array.from({length:n},(_,i)=>{const c=f(i);return{time:1.5e9+i*D,open:c,high:c*1.01,low:c*0.99,close:c,volume:1}});
let c=cycleAt(mk(1500,()=>100),1499);
ok(c.m.w200.s===0&&Math.abs(c.m.mayer.v-1)<1e-9&&c.m.pi.s===Math.round((0.5-0.45)/0.55*100),'cycle: flat price = 1x averages');
ok(Math.abs(c.m.dd.v-(1-100/101))<1e-9,'cycle: drawdown measured from the highest high');
c=cycleAt(mk(1500,i=>i<1300?100:100*Math.pow(1.01,i-1299)),1499);   // a steep run-up at the end
ok(c.m.mayer.s>=90&&c.m.dd.s>=95&&c.score>=70,'cycle: steep run-up reads hot ('+c.score+')');
c=cycleAt(mk(1500,i=>i<1200?100*Math.pow(1.003,i):100*Math.pow(1.003,1199)*Math.pow(0.996,i-1199)),1499);   // long rise then a deep fall
ok(c.m.dd.v>0.6&&c.score<45,'cycle: deep fall reads cool ('+c.score+')');
ok(cycleAt(mk(150,()=>1),149).m.w200===null&&cycleAt(mk(150,()=>1),149).score===null,'cycle: short history gives no score');
ok(cycleZone(10)[0]==='cold'&&cycleZone(50)[0]==='mid'&&cycleZone(85)[0]==='hot'&&cycleZone(null)===null,'cycle zones');
const ph=t=>cyclePhase(Date.UTC(2024,3,20)+t*864e5);
ok(ph(100).k==='early'&&ph(500).k==='peak'&&ph(700).k==='post'&&ph(919).k==='bottom'&&ph(1200).k==='recovery'&&ph(919).days===919,'cycle phases by days since halving');
ok(cyclePhase(Date.UTC(2017,11,17)).k==='peak'&&cyclePhase(Date.UTC(2021,10,10)).k==='peak'&&cyclePhase(Date.UTC(2018,11,15)).k==='bottom'&&cyclePhase(Date.UTC(2022,10,21)).k==='bottom','cycle phases match past tops and lows');
ok(cyclePhase(Date.UTC(2010,0,1))===null,'cycle: before the first halving');}
// Fibonacci levels (information only): swings, the measured move, retracement maths and look-ahead
{const mkc=ps=>ps.map((p,i)=>({time:i*3600,open:p,high:p+0.5,low:p-0.5,close:p,volume:1}));
const path=[];for(let i=0;i<20;i++)path.push(100);for(let i=0;i<=20;i++)path.push(100+i*5);for(let i=1;i<=8;i++)path.push(200-i*5);   // flat, up 100 -> 200, back to 160
const cs=mkc(path);
const z=zigzag(cs,20,0);ok(z.length>=2&&Math.abs(z[z.length-1].p-159.5)<1e-9&&z[z.length-1].open,'zigzag: last swing is the open pullback low');
let f=fibLevels(cs,5);   // threshold 15
ok(f&&f.dir===1&&Math.abs(f.a.p-99.5)<1e-9&&Math.abs(f.b.p-200.5)<1e-9,'fib: measures the main up-move, not the smaller pullback');
const l618=f.levels.find(l=>l.r===0.618),x16=f.levels.find(l=>l.ext&&Math.abs(l.r+0.618)<1e-9);
ok(Math.abs(l618.p-(200.5-101*0.618))<1e-9&&Math.abs(x16.p-(99.5+101*1.618))<1e-9,'fib: 61.8% retracement and 161.8% extension prices');
ok(Math.abs(f.retr-(200.5-160)/101)<1e-9&&fibZone(f.retr)==='38.2–50%','fib: price has given back about 40% (38.2–50% zone)');
ok(f.above&&f.above.name==='38.2%'&&f.below&&f.below.name==='50%','fib: next levels above and below');
// a pullback bigger than the move becomes the new main move (down)
const p2=path.concat(Array.from({length:30},(_,i)=>155-i*5));f=fibLevels(mkc(p2),5);
ok(f&&f.dir===-1&&Math.abs(f.b.p-(10-0.5))<1e-9,'fib: once the drop is bigger than the up-move, the drop is measured');
// breakout past the swing high reads as an extension
const p3=path.concat(Array.from({length:12},(_,i)=>165+i*5));f=fibLevels(mkc(p3),5);
ok(f&&f.dir===1&&Math.abs(f.a.p-159.5)<1e-9&&Math.abs(f.b.p-220.5)<1e-9&&f.breakout&&Math.abs(f.brk-200.5)<1e-9,'fib: new high past the old swing high reads as a breakout');
ok(fibLevels(cs,5).breakout===false,'fib: a pullback is not a breakout');
ok(fibLevels(mkc(path.slice(0,30)),5)===null,'fib: under 40 candles gives nothing');ok(fibLevels(cs,0)===null&&fibLevels([],5)===null,'fib: no ATR or no candles gives nothing');
ok(fibZone(-0.1)==='Past the swing end'&&fibZone(0.1)==='Under 23.6%'&&fibZone(0.7)==='61.8–78.6%'&&fibZone(1.2)==='Past 100%'&&fibZone(NaN)===null,'fibZone bands');
// no look-ahead: levels at a past candle equal levels computed on candles up to that point
const p=state.pairs[0],dc=demoCandles(p,'1h',600),S=computeSeries(dc);let same=true;
for(const L of [250,333,420,599]){const a=fibLevels(dc.slice(0,L+1),S.at[L]),b=fibLevels(dc.slice(0,L+1).map(k=>({...k})),S.at[L]);if(JSON.stringify(a)!==JSON.stringify(b))same=false;
  if(a)for(const l of a.levels)if(!(isFinite(l.p)&&l.p>0))same=false;
  if(a&&(a.a.i>L||a.b.i>L))same=false}
ok(same,'fib: uses only candles up to the reading, all prices finite');}
ok(oddsKey('15m',1,72,true)==='15m|long|70+|1'&&oddsKey('4h',-1,49,false)==='4h|short|<50|0'&&oddsKey('1h',1,50,false)==='1h|long|50-69|0','oddsKey');
// the onEntry hook only observes: same trades with and without it
const p=demoPairs()[2],cs=demoCandles(p,'1h',900),hcs=demoCandles(p,'4h',900),o={plan:'split',minConf:0,fee:0.0005,slip:0.0002,maxHold:96};
let seen=0;const a=backtestSeries(cs,hcs,p,'1h',o),b=backtestSeries(cs,hcs,p,'1h',Object.assign({},o,{onEntry:(t,x)=>{if(x.an&&x.rc&&x.i===t.i)seen++}}));
ok(a.length>0&&JSON.stringify(a)===JSON.stringify(b)&&seen===b.length,'onEntry hook does not change the backtest');}
// order book summary
{const b=bookStats([[99.5,1000],[98.5,2000],[97,5000]],[[100.5,1500],[101.5,500],[103,9000]]);
ok(b&&Math.abs(b.mid-100)<1e-9&&Math.abs(b.spread-0.01)<1e-12,'bookStats: mid and spread');
ok(b.d1.bid===1000&&b.d1.ask===1500&&b.d2.bid===3000&&b.d2.ask===2000,'bookStats: depth within 1% and 2%');
ok(Math.abs(b.covered-0.03)<1e-9,'bookStats: how far the loaded levels reach');
ok(bookStats([[101,5]],[[100,5]])===null&&bookStats([],[[1,1]])===null&&bookStats([[1,NaN]],[[2,1]])===null,'bookStats: crossed, empty or junk book');
const lv=(s,k)=>[100*(1+s*0.001*(k+1)),k===4?20000:1000],w=bookStats(Array.from({length:10},(_,k)=>lv(-1,k)),Array.from({length:10},(_,k)=>lv(1,k)));
ok(w.walls.length===2&&w.walls.every(x=>x.usd===20000)&&w.walls.some(x=>x.side==='buy')&&w.walls.some(x=>x.side==='sell'),'bookStats: finds one large order on each side');
ok(bookStats([[99,1000],[98,1100]],[[101,900],[102,1000]]).walls.length===0,'bookStats: no walls in an even book');}
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
// economic event guard
const N0=1e9,ev=(t,c,dt,i)=>({t,c,d:N0+dt,i:i||'High'});
ok(eventGuard([],N0)===null&&eventGuard(null,N0)===null,'no calendar, no warning');
ok(eventGuard([ev('CPI m/m','USD',31*60)],N0)===null,'31 min ahead is outside the window');
let gd=eventGuard([ev('CPI m/m','USD',30*60)],N0);ok(gd&&gd.mins===30&&gd.until===N0+3600,'exactly 30 min ahead warns');
gd=eventGuard([ev('Non-Farm Employment Change','USD',-12*60)],N0);ok(gd&&gd.mins===-12,'12 min after still warns');
ok(eventGuard([ev('CPI y/y','GBP',60),ev('Retail Sales','USD',60,'Medium')],N0)===null,'only high-impact US events count');
gd=eventGuard([ev('FOMC Statement','USD',25*60),ev('CPI m/m','USD',5*60),ev('Core CPI m/m','USD',5*60),ev('CPI m/m','USD',5*60)],N0);
ok(gd&&gd.mins===5&&gd.names.join('|')==='CPI m/m|Core CPI m/m','nearest event wins and same-minute events group');
ok(eventGuard([ev('BOJ Policy Rate','JPY',10*60)],N0)===null,'Japan news ignored by default');
gd=eventGuard([ev('BOJ Policy Rate','JPY',10*60),ev('Main Refinancing Rate','EUR',10*60)],N0,0,EV_CC_ALL);ok(gd&&gd.mins===10&&gd.cc.join('|')==='JPY|EUR','other countries count when switched on');
ok(eventGuard([ev('CPI y/y','GBP',60)],N0,0,EV_CC_ALL)===null,'UK still ignored with the wider list');
// news data cleaner (hostile or broken news.json)
ok(cleanNews(null)===null&&cleanNews({items:'x'})===null,'news without an item list is rejected');
let cn=cleanNews({items:[null,5,{t:'ok',d:N0,u:'https://a',c:'BTC',g:['Hack',7,{}],x:{}},{t:'',d:N0},{t:'no date',d:'today'},{t:'x'.repeat(999),d:N0,s:['a']}],
  calendar:[{t:'CPI',c:'USD',d:N0,i:'High'},{t:'bad',d:'x'},null],fng:{v:'50'},sources:'nope'});
ok(cn.items.length===2&&cn.items[0].c.length===0&&cn.items[0].g.join()==='Hack'&&cn.items[0].x===''&&cn.items[1].t.length===300&&cn.items[1].s==='','news items cleaned to plain strings and arrays');
ok(cn.calendar.length===1&&cn.fng===null&&Array.isArray(cn.sources)&&cn.sources.length===0,'calendar, fear & greed and sources cleaned');
// later-today planner
let lt=eventsLater([ev('FOMC Statement','USD',5*3600),ev('CPI m/m','USD',2*3600),ev('Core CPI m/m','USD',2*3600),ev('Retail Sales','USD',3*3600,'Medium')],N0,N0+6*3600);
ok(lt.length===2&&lt[0].d===N0+7200&&lt[0].names.length===2&&lt[1].names[0]==='FOMC Statement','later today: grouped, soonest first, high impact only');
ok(eventsLater([ev('CPI m/m','USD',20*60),ev('CPI m/m','USD',-3600)],N0,N0+6*3600).length===0,'inside the warning window or past is not listed');
ok(eventsLater([ev('CPI m/m','USD',7*3600)],N0,N0+6*3600).length===0,'after midnight is not listed');
ok(eventsLater([ev('BOJ Policy Rate','JPY',3600)],N0,N0+6*3600).length===0&&eventsLater([ev('BOJ Policy Rate','JPY',3600)],N0,N0+6*3600,0,EV_CC_ALL).length===1,'later today follows the country switch');
// import my trades: tolerant CSV parsing and stats (all on the device)
{let rows=parseCSV('a,"b,c",d\\r\\n"x ""y""",2,\\n\\n3;4');ok(rows.length===3&&rows[0][1]==='b,c'&&rows[1][0]==='x "y"'&&rows[1][2]==='','csv: quotes, escaped quotes, CRLF, blank lines');
ok(parseCSV('﻿a;b;c\\n1;2;3')[1].join('|')==='1|2|3','csv: BOM and semicolons');
ok(parseCSV('a\\tb\\n1\\t2')[1][1]==='2','csv: tabs');
let c=tradeCols(['Contract','Side','Open Time','Close Time','Position Size','Avg. Entry Price','Avg. Close Price','Realized PnL (USDT)','Fee']);
ok(c.contract===0&&c.side===1&&c.open===2&&c.close===3&&c.size===4&&c.entry===5&&c.exit===6&&c.pnl===7&&c.fee===8,'columns matched by meaning: '+JSON.stringify(c));
c=tradeCols(['time','contract','side','pnl','pnl_pnl','pnl_fund','pnl_fee','text','max_size','first_open_time','long_price','short_price']);
ok(c.close===0&&c.pnl===3&&c.fee===6&&c.open===9&&c.size===8&&c.longp===10&&c.shortp===11,'Gate API position_close names: '+JSON.stringify(c));
ok(tradeNum('1,038.50')===1038.5&&tradeNum('−602.1 USDT')===-602.1&&tradeNum('(12.5)')===-12.5&&tradeNum('+3')===3&&isNaN(tradeNum('')),'numbers: commas, unicode minus, brackets, units');
ok(tradeTime('1760000000')===1760000000000&&tradeTime('1760000000123')===1760000000123,'times: seconds and milliseconds');
ok(tradeTime('2026-10-19 14:32:10 UTC')===Date.UTC(2026,9,19,14,32,10)&&tradeTime('2026/10/19 14:32')===new Date(2026,9,19,14,32).getTime()&&isNaN(tradeTime('soon')),'times: text dates (UTC and local)');
ok(tradeRoot('BTC_USDT')==='BTC'&&tradeRoot('ETHUSDT Perpetual')==='ETH'&&tradeRoot('1000PEPE-USDT')==='1000PEPE'&&tradeRoot('SOL/USDT')==='SOL','contract names to coin');
ok(tradeSide('Short')==='short'&&tradeSide('dual_long')==='long'&&tradeSide('Close Long')==='long'&&tradeSide('',-5)==='short'&&tradeSide('?',0)===null,'sides from words or size sign');
let csv='Gate futures export\\nContract,Side,Open Time,Close Time,Size,Entry Price,Close Price,Realized PnL,Fee\\n'+
  'BTC_USDT,Long,2026-10-05 01:00:00 UTC,2026-10-05 08:00:00 UTC,1,60000,60600,60.00,-1.2\\n'+
  'ETH_USDT,Short,2026-10-06 13:00:00 UTC,2026-10-06 13:30:00 UTC,2,2500,2510,-20,-1\\n'+
  'ETH_USDT,Short,2026-10-07 13:00:00 UTC,2026-10-07 15:00:00 UTC,2,2500,2400,"1,000.00",-1\\n'+
  'SOL_USDT,Long,,2026-10-08 20:00:00 UTC,5,150,140,-1038,-2\\n'+
  ',Long,2026-10-08 20:00:00 UTC,2026-10-08 20:00:00 UTC,1,1,1,5,0\\nXRP_USDT,Long,2026-10-08,soon,1,1,1,abc,0\\n';
let r=parseTrades(csv),T=r.trades;
ok(T.length===4&&r.skipped===2&&!r.error,'parse: 4 trades, 2 broken rows skipped ('+T.length+','+r.skipped+')');
ok(T[0].root==='BTC'&&T[0].side==='long'&&T[0].entry===60000&&T[0].exit===60600&&T[0].fee===1.2&&T[0].t0===Date.UTC(2026,9,5,1),'parse: fields read');
ok(T[3].t0===null&&T[3].t1===Date.UTC(2026,9,8,20),'parse: missing open time kept as unknown');
r=parseTrades('contract,side,long_price,short_price,pnl,time\\nBTC_USDT,short,100,110,-5,1760000000');
ok(r.trades.length===1&&r.trades[0].entry===110&&r.trades[0].exit===100,'parse: Gate long_price/short_price mapped by side');
ok(parseTrades('a,b\\n1,2').error&&parseTrades('').trades.length===0,'parse: unknown file gives a plain error');
let s=tradeStats(T,t=>{const d=new Date(t);return{h:d.getUTCHours(),w:(d.getUTCDay()+6)%7}});
ok(s.n===4&&Math.abs(s.win-0.5)<1e-9&&Math.abs(s.pnl-2)<1e-9&&s.worst.root==='SOL'&&Math.abs(s.fees-5.2)<1e-9,'stats: win rate, total, worst loss, fees');
ok(Math.abs(s.avgWin-530)<1e-9&&Math.abs(s.avgLoss-529)<1e-9&&Math.abs(s.rr-530/529)<1e-9,'stats: average win vs loss');
ok(s.side.map(x=>x.k+x.n).join()==='Long2,Short2'&&s.coin[0].k==='ETH'&&s.coin[0].n===2,'stats: by side and coin');
ok(s.hold.map(x=>x.k+x.n).join()==='Under 1 hour1,1–4 hours1,4–12 hours1','stats: holding time (unknown open time left out)');
ok(s.hour.find(x=>x.k==='12am–4am').n===1&&s.day.find(x=>x.k==='Mon').n===1&&s.day.find(x=>x.k==='Thu').n===1,'stats: hour band and weekday of opening');
ok(readingVsSide('long','long')==='Reading agreed'&&readingVsSide('long','short')==='Reading pointed the other way'&&readingVsSide('short','hold')==='Wait or no setup'&&readingVsSide('short','')===null,'reading vs side');
T[0].r1h='long';T[1].r1h='long';s=tradeStats(T);ok(s.r1h.length===2&&s.r1h[0].k==='Reading agreed'&&s.r1h[1].n===1,'stats: grouped by the 1H reading');
let cl=cleanTrades([null,{root:'BTC',side:'long',pnl:5,t1:1e12,t0:2e12,fee:-1,r1h:7},{root:'X',side:'up',pnl:1,t1:1},{root:'Y',side:'short',pnl:'5',t1:1},'x']);
ok(cl.length===1&&cl[0].t0===null&&cl[0].fee===1&&cl[0].r1h===undefined&&cleanTrades('junk').length===0,'saved trades cleaned');}
const st=simStats([],2);ok(st.n===0,'empty stats');
ok(n>50,'backtest produced too few trades: '+n);
console.log('engine tests: '+pass+' passed, '+fail+' failed ('+n+' simulated trades in '+(Date.now()-t0)+' ms)');
if(fail)process.exit(1);
`;
eval(code);
