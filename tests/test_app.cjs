const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();const el=id=>{if(!elements.has(id))elements.set(id,{value:'',classList:{toggle(){}},textContent:'',innerHTML:''});return elements.get(id)};
const storage=new Map();
const context=vm.createContext({document:{getElementById:el,querySelectorAll:()=>[]},localStorage:{getItem:k=>storage.get(k)||null,setItem(k,v){storage.set(k,v)}},navigator:{},location:{protocol:'http:'},Intl,Date,URL,Blob,console,setTimeout(){},setInterval(){},fetch:async()=>{throw Error('offline')}});
vm.runInContext(fs.readFileSync('research_ui.js','utf8'),context);
vm.runInContext(fs.readFileSync('tracker.js','utf8'),context);
vm.runInContext(fs.readFileSync('app.js','utf8'),context);
const run=s=>vm.runInContext(s,context);
assert.equal(run("result({halftime:{result:'draw'}},'1h')"),'draw');
assert.equal(run("result({completed:true,home:{score:110},away:{score:100}},'ft')"),'home');
assert.equal(run("result({completed:false,home:{score:110},away:{score:100}},'ft')"),null);
assert.equal(run("result({completed:true,home:{score:null},away:{score:100}},'ft')"),null);
run("entries=[{id:'1',league:'epl',halftime:{result:'draw'}}];log=[{id:'1',league:'epl',market:'1h',selection:'draw'}];grade()");
assert.equal(run('log[0].grade'),'Win');
run("log[0].selection='home';grade()");assert.equal(run('log[0].grade'),'Loss');
console.log('PASS: frontend 1H/NBA grading and missing scores');

// A started pick remains on Today, with an explicit LIVE indicator.
run(`currentView='today';sport='nba';$('date').value=pacific(Date.now());$('search').value='';
entries=Array.from({length:9},(_,i)=>({id:String(i),league:'nba',date_utc:pacific(Date.now())+'T20:00:00Z',state:'in',completed:false,home:{name:'Home '+i},away:{name:'Away '+i},source_url:'https://www.espn.com/nba/game/_/gameId/'+i}));
publicPicks=[{id:'live-pick',game_id:'0',league:'nba',game_date:entries[0].date_utc,label:'Visible started pick',market:'nplus',generated_utc:new Date().toISOString(),grade:'Pending'}];draw();`);
assert.match(el('shortlist').innerHTML,/Visible started pick/);
assert.match(el('shortlist').innerHTML,/live-indicator/);
assert.equal((el('nbaSlateGames').innerHTML.match(/data-nba-game=/g)||[]).length,9);
// Changing another tab's sport/search cannot hide Today's picks.
run("$('search').value='Visible';captureFilters();setView('history');setSport('nhl');$('search').value='Other sport';captureFilters();setView('today')");
assert.equal(run('sport'),'nba');assert.equal(el('search').value,'Visible');
assert.match(el('shortlist').innerHTML,/Visible started pick/);
// Unpriced picks are labelled RESEARCH ONLY.
assert.match(el('shortlist').innerHTML,/RESEARCH ONLY/);
// Completed picks leave the active Today view but remain in History with their grade.
run("entries[0].completed=true;publicPicks[0].grade='Win';publicPicks[0].game_date=new Date(Date.now()-3600e3).toISOString();draw()");
assert.doesNotMatch(el('shortlist').innerHTML,/Visible started pick/);
assert.match(el('coverage').textContent,/1 completed pick has moved to History/);
run("$('historyDate').value='';$('historyType').value='all';$('historyGrade').value='all';$('search').value='';drawHistory()");
assert.match(el('historyRows').innerHTML,/Visible started pick/);assert.match(el('historyRows').innerHTML,/Win/);
// A soccer 1H pick settles at halftime, before the match is final.
run("entries.push({id:'ht',league:'epl',date_utc:new Date().toISOString(),state:'in',completed:false,home:{name:'H'},away:{name:'A'}})");
assert.equal(run("activePicks([{id:'s',league:'epl',game_id:'ht',market:'1h',grade:'Loss',game_date:new Date().toISOString()}],pacific(Date.now())).length"),0);
assert.equal(run("activePicks([{id:'s',league:'epl',game_id:'ht',market:'1h',grade:'Pending',game_date:new Date().toISOString()}],pacific(Date.now())).length"),1);
// Pacific midnight rollover: views on the old day advance, custom dates are kept,
// and a game that started before midnight stays active until it settles.
run(`slateToday='2026-11-07';$('date').value='2026-11-07';viewFilters.history={sport:'all',date:'2026-11-01',query:''};viewFilters.scores={sport:'all',date:'2026-11-07',query:''}`);
assert.equal(run("rollover(Date.parse('2026-11-08T08:05:00Z'))"),true);
assert.equal(el('date').value,'2026-11-08');assert.equal(run('viewFilters.scores.date'),'2026-11-08');assert.equal(run('viewFilters.history.date'),'2026-11-01');
assert.equal(run("rollover(Date.parse('2026-11-08T08:06:00Z'))"),false);
assert.equal(run("activePicks([{id:'late',league:'nhl',game_id:'x',market:'ft',grade:'Pending',game_date:'2026-11-08T06:30:00Z'}],'2026-11-08',Date.parse('2026-11-08T08:05:00Z')).length"),1);
assert.equal(run("activePicks([{id:'old',league:'nhl',game_id:'x',market:'ft',grade:'Pending',game_date:'2026-11-06T03:00:00Z'}],'2026-11-08',Date.parse('2026-11-08T08:05:00Z')).length"),0);
run("slateToday=pacific(Date.now())");
console.log('PASS: settled picks move to History, 1H settles at halftime, Pacific midnight rollover');
// Raw model thresholds do not disappear at tipoff.
run("renderProps([{player:'Saved player',player_id:'1',game_id:'1',league:'nba',game_date:entries[1].date_utc,threshold:20,stat:'points',injury:{status:'Unconfirmed'},grade:'Pending'}])");
assert.match(el('props').innerHTML,/Saved player/);assert.match(el('props').innerHTML,/LIVE/);
// Partial refreshes retain old rows and cannot regress a verified grade.
assert.equal(run("mergeArchive([{id:'kept',grade:'Win',actual_value:25}],[{id:'kept',grade:'Pending'}],'id')[0].grade"),'Win');
assert.equal(run("mergeArchive([{id:'kept'}],[],'id').length"),1);
console.log('PASS: live/final pick retention, all-nine NBA coverage and independent tab filters');
(async()=>{
  const pending=[];
  context.fetch=()=>new Promise(resolve=>pending.push(resolve));
  const older=run('refreshFeed()'),newer=run('refreshFeed()');
  function response(name,label){return {ok:true,json:async()=>({schema_version:1,generated_utc:new Date().toISOString(),...(name==='picks'?{picks:[{id:'race',league:'nba',game_date:new Date().toISOString(),label}]}:name==='prediction_log'?{predictions:[]}:{games:[]})})}}
  const names=['yesterday','latest','picks','prediction_log'];
  names.forEach((n,i)=>pending[i+4](response(n,'Newer selection')));await newer;
  names.forEach((n,i)=>pending[i](response(n,'Older selection')));await older;
  assert.equal(run("publicPicks.find(p=>p.id==='race').label"),'Newer selection');
  run('cacheResearch()');
  const cached=JSON.parse(storage.get('matchlab_research_cache_v1'));
  assert(cached.publicPicks.some(p=>p.id==='live-pick'));
  assert(cached.publicPicks.some(p=>p.id==='race'));
  console.log('PASS: overlapping refreshes cannot replace new picks; research is cached across reloads');
})().catch(err=>{console.error(err);process.exitCode=1});

// A static scheduled snapshot cannot erase a newer in-game score or final.
run(`entries=[{id:'fresh',league:'nba',date_utc:'2026-11-07T00:00:00Z',state:'in',completed:false,clock:'5:00',home:{name:'H',score:70},away:{name:'A',score:60},score_observed_utc:'2026-11-07T01:00:00Z'}];
merge([{id:'fresh',league:'nba',date_utc:'2026-11-07T00:00:00Z',state:'pre',completed:false,home:{name:'H',score:null},away:{name:'A',score:null}}],'2026-11-07T00:30:00Z');`);
assert.equal(run('entries[0].home.score'),70);assert.equal(run('entries[0].state'),'in');
run("entries[0].completed=true;entries[0].state='post';merge([{id:'fresh',league:'nba',date_utc:'2026-11-07T00:00:00Z',state:'in',completed:false,home:{name:'H',score:1},away:{name:'A',score:1}}],'2026-11-07T02:00:00Z')");
assert.equal(run('entries[0].completed'),true);assert.equal(run('entries[0].home.score'),70);
// Only a provider in-progress state earns LIVE; scheduled time alone does not.
run("entries=[{id:'scheduled',league:'nba',date_utc:'2026-01-01T00:00:00Z',state:'pre',completed:false,home:{name:'H'},away:{name:'A'}}]");
assert.notEqual(run("pickState({game_id:'scheduled',league:'nba',game_date:'2026-01-01T00:00:00Z'})"),'LIVE');
assert.equal(run("scoreNumber('')"),null);assert.equal(run('scoreNumber(null)'),null);assert.equal(run("scoreNumber('0')"),0);
run(`sampleEvent={id:'n',date:'2026-11-07T01:00:00Z',status:{period:2,displayClock:'4:00',type:{name:'STATUS_IN_PROGRESS',state:'in',completed:false}},competitions:[{competitors:[{homeAway:'home',team:{id:'h',displayName:'Home'},score:'42',linescores:[{value:20}]},{homeAway:'away',team:{id:'a',displayName:'Away'},score:'39',linescores:[{value:19}]}]}]}`);
assert.equal(run("normalizeLiveEvent(sampleEvent,'nba').state"),'in');
assert.equal(run("normalizeLiveEvent(sampleEvent,'nhl').halftime"),null);
run("cacheResearch()");
assert(!storage.get('matchlab_research_cache_v1').includes('matchlab_private_bets'));
console.log('PASS: minute-score normalization, last-good score preservation, strict LIVE status and private-cache separation');
