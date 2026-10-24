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
