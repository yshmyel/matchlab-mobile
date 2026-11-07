/** @OnlyCurrentDoc
 * Bound to the user's existing tracker. Pull-only: no private rows leave Google.
 */
const ML_RESEARCH_HEADERS=['Key','Generated UTC','Sport','Game / Player','Market','Selection','Probability','Model','Grade','Actual','Source / Context','Updated UTC','Status','Odds'];
const ML_PICK_HEADERS=['Key','Published UTC','Pacific date','Sport','Matchup','Selection','Market','Status','Value status','Grade','Result','Result basis','Grade source','Graded UTC','Picked by','Updated UTC'];
const ML_SETTLED=['Win','Loss','Push','DNP','Not applicable'];
const ML_MAX_AGE_MS=7200000;
// Reject missing, unparseable, future (>5 min skew) or stale timestamps; an invalid date must never pass as fresh.
function mlFresh_(ts,now,maxMs){const t=Date.parse(ts);return typeof ts==='string'&&Number.isFinite(t)&&t<=now+300000&&now-t<=maxMs;}
function mlMarket_(p){return {nplus:p.threshold+'+ '+p.stat,'n+':p.threshold+'+ '+p.stat,'1h':'1H 1X2',ft:'Full-game ML (incl. OT/SO)',total:'Full-game total '+(p.line??''),pass:'PASS (no selection)'}[p.market]||String(p.market||'');}
function mlValue_(p){return p.value_status==='VALUE ASSESSED'?'VALUE ASSESSED':'RESEARCH ONLY · no verified price';}
function mlResult_(p){if(p.market==='pass'){const r=p.official_result;return r?'Official '+r.final_score.away+'–'+r.final_score.home+(r.halftime_score?' (HT '+r.halftime_score.away+'–'+r.halftime_score.home+')':''):'';}
 const s=p.actual_score;return p.actual_value??(s?s.away+'–'+s.home+' '+(p.actual??''):p.actual??'');}
// Upsert by key; a settled sheet row is never regressed by an older Pending copy, and duplicate keys collapse to one row.
function mlMerge_(old,incoming,gradeIdx){const map=new Map(old.filter(r=>r[0]).map(r=>[r[0],r]));for(const row of incoming){const prior=map.get(row[0]);
 if(prior&&ML_SETTLED.includes(prior[gradeIdx])&&!ML_SETTLED.includes(row[gradeIdx]))continue;map.set(row[0],row.map(mlSafe_));}return Array.from(map.values());}
function mlWrite_(s,rows,width){const prev=Math.max(0,s.getLastRow()-1);if(rows.length){if(s.getMaxRows()<rows.length+1)s.insertRowsAfter(s.getMaxRows(),rows.length+1-s.getMaxRows());s.getRange(2,1,rows.length,width).setValues(rows);}
 if(prev>rows.length)s.getRange(rows.length+2,1,prev-rows.length,width).clearContent();}
function mlPickRows_(feed){return feed.picks.map(p=>[p.id,p.published_utc||p.generated_utc,mlPacific_(p.game_date),p.league,p.match||'',p.label||p.selection,mlMarket_(p),p.status||'',mlValue_(p),p.grade||'Pending',mlResult_(p),p.result_basis||'',p.grade_source||p.official_result_source||'',p.graded_utc||p.official_result_utc||'',p.picked_by||'',feed.updated_utc]);}
function mlPacific_(iso){const t=Date.parse(iso);if(!Number.isFinite(t))return '';return new Date(t).toLocaleDateString('en-CA',{timeZone:'America/Los_Angeles'});}
const ML_PERF_HEADERS=['Sport / League','Model','Test n','Accuracy','Log loss','Brier','Baseline log loss','Status','As of'];
function onOpen(){SpreadsheetApp.getUi().createMenu('MatchLab').addItem('Refresh public research','matchLabRefresh').addItem('Enable 30-minute updates','matchLabInstall').addItem('Disable updates','matchLabDisable').addSeparator().addItem('Sync agent messages','matchLabAgentSync').addItem('Enable 15-minute agent bridge','matchLabAgentInstall').addItem('Disable agent bridge','matchLabAgentDisable').addToUi();}
function matchLabInstall(){matchLabRefresh();matchLabDisable();ScriptApp.newTrigger('matchLabRefresh').timeBased().everyMinutes(30).create();mlStatus_('Enabled: 30-minute trigger; best-effort Google scheduling');}
function matchLabDisable(){ScriptApp.getProjectTriggers().filter(t=>t.getHandlerFunction()==='matchLabRefresh').forEach(t=>ScriptApp.deleteTrigger(t));mlStatus_('Disabled');}
function mlBook_(){const s=SpreadsheetApp.getActiveSpreadsheet();if(!s)throw Error('This script must be bound to the tracker spreadsheet.');return s;}
function mlStatus_(status){const s=mlBook_().getSheetByName('MatchLab Integration');if(s){s.getRange('B3').setValue(status);s.getRange('B4').setValue(new Date().toISOString());}}
function mlUrl_(base){if(typeof base!=='string'||!/^https:\/\/yshmyel\.github\.io\/matchlab-mobile\/$/.test(base))throw Error('Enter the verified HTTPS MatchLab Pages URL (trailing slash) in MatchLab Integration!B2.');return base;}
function mlFetch_(url){const r=UrlFetchApp.fetch(url,{muteHttpExceptions:true,followRedirects:false});if(r.getResponseCode()!==200)throw Error('Feed HTTP '+r.getResponseCode());const text=r.getContentText();if(text.length>5000000)throw Error('Feed unexpectedly large');const f=JSON.parse(text);if(f.schema_version!==1)throw Error('Unsupported schema');return f;}
function mlSafe_(v){if(v===null||v===undefined)return '';if(typeof v==='number')return Number.isFinite(v)?v:'';const s=String(v);return /^[=+@-]/.test(s)?"'"+s:s;}
function mlSheet_(name,headers){const b=mlBook_();const s=b.getSheetByName(name)||b.insertSheet(name);const existing=s.getRange(1,1,1,headers.length).getValues()[0];if(existing.some(Boolean)&&existing.some((v,i)=>v!==headers[i]))throw Error('Unexpected headers in '+name+'; refusing to overwrite');s.getRange(1,1,1,headers.length).setValues([headers]);s.setFrozenRows(1);return s;}
function mlResearchRows_(log){return log.predictions.map(p=>[p.key,p.generated_utc,p.league,p.league==='nba'?p.player:p.home+' vs '+p.away,mlMarket_(p),p.selection,p.probability??p.probabilities?.[p.selection]??'',p.model_version,p.grade||'Pending',p.actual_value??p.actual??'',p.league==='nba'?'ESPN player logs; conditional on playing':'open-matchday reported HT; provisional model',log.updated_utc,p.status,mlValue_(p)]);}
// Optional: GitHub drops most scheduled runs, so this 30-minute trigger can request
// a refresh. Only acts when Script Property GITHUB_DISPATCH_TOKEN holds a fine-grained
// token limited to this repository with Actions: read and write. Never fails the sync.
const ML_DISPATCH_URL='https://api.github.com/repos/yshmyel/matchlab-mobile/actions/workflows/pages.yml/dispatches';
function mlShouldKick_(updatedUtc,now){const t=Date.parse(updatedUtc);return !Number.isFinite(t)||now-t>40*60000;}
function mlKick_(updatedUtc){try{const token=PropertiesService.getScriptProperties().getProperty('GITHUB_DISPATCH_TOKEN');if(!token||!mlShouldKick_(updatedUtc,Date.now()))return false;
 const r=UrlFetchApp.fetch(ML_DISPATCH_URL,{method:'post',contentType:'application/json',payload:JSON.stringify({ref:'main'}),headers:{Authorization:'Bearer '+token,Accept:'application/vnd.github+json'},muteHttpExceptions:true,followRedirects:false});
 return r.getResponseCode()===204;}catch(e){return false;}}
function matchLabRefresh(){const lock=LockService.getDocumentLock();if(!lock.tryLock(1000))return;try{
 const config=mlBook_().getSheetByName('MatchLab Integration');if(!config)throw Error('Missing MatchLab Integration configuration');const base=mlUrl_(config.getRange('B2').getValue());
 const log=mlFetch_(base+'data/prediction_log.json');const perf=mlFetch_(base+'data/performance.json');if(!Array.isArray(log.predictions)||!perf.soccer)throw Error('Malformed research feed');
 mlKick_(log.updated_utc);
 const picks=mlFetch_(base+'data/picks.json');if(!Array.isArray(picks.picks))throw Error('Malformed picks feed');
 if(!mlFresh_(log.updated_utc,Date.now(),ML_MAX_AGE_MS)||!mlFresh_(picks.updated_utc,Date.now(),ML_MAX_AGE_MS))throw Error('Research feed is stale or undated; keeping existing rows');
 const s=mlSheet_('MatchLab Research',ML_RESEARCH_HEADERS);const old=s.getLastRow()>1?s.getRange(2,1,s.getLastRow()-1,ML_RESEARCH_HEADERS.length).getValues():[];
 const rows=mlMerge_(old,mlResearchRows_(log),8);mlWrite_(s,rows,ML_RESEARCH_HEADERS.length);
 const ps=mlSheet_('MatchLab Picks',ML_PICK_HEADERS);const oldPicks=ps.getLastRow()>1?ps.getRange(2,1,ps.getLastRow()-1,ML_PICK_HEADERS.length).getValues():[];
 const pickRows=mlMerge_(oldPicks,mlPickRows_(picks),9);mlWrite_(ps,pickRows,ML_PICK_HEADERS.length);
 const per=mlSheet_('MatchLab Performance',ML_PERF_HEADERS);const out=[];
 for(const [league,m] of Object.entries(perf.soccer)){out.push([league,m.model||'HT unavailable',m.test?.n??0,m.test?.accuracy??'',m.test?.log_loss??'',m.test?.brier??'',m.baseline_test?.log_loss??'',m.status,perf.generated_utc]);}
 for(const p of perf.nba||[]){const m=p.backtest;out.push(['NBA '+p.player+' '+p.threshold+'+ '+p.stat,m.model||'Unavailable',m.test?.n??0,m.test?.accuracy??'',m.test?.log_loss??'',m.test?.brier??'','',m.status,perf.generated_utc]);}
 if(out.length){if(per.getMaxRows()<out.length+1)per.insertRowsAfter(per.getMaxRows(),out.length+1-per.getMaxRows());per.getRange(2,1,out.length,ML_PERF_HEADERS.length).setValues(out.map(r=>r.map(mlSafe_)));if(per.getLastRow()>out.length+1)per.getRange(out.length+2,1,per.getLastRow()-out.length-1,ML_PERF_HEADERS.length).clearContent();}
 mlStatus_('Last refresh succeeded; '+rows.length+' model snapshots (MatchLab Research) and '+pickRows.length+' editorial picks (MatchLab Picks). Trigger state unchanged.');
 }catch(e){mlStatus_('ERROR: '+e.message);throw e;}finally{lock.releaseLock();}}
