/** @OnlyCurrentDoc
 * Bound to the user's existing tracker. Pull-only: no private rows leave Google.
 */
const ML_RESEARCH_HEADERS=['Key','Generated UTC','Sport','Game / Player','Market','Selection','Probability','Model','Grade','Actual','Source / Context','Updated UTC','Status','Odds'];
const ML_PERF_HEADERS=['Sport / League','Model','Test n','Accuracy','Log loss','Brier','Baseline log loss','Status','As of'];
function onOpen(){SpreadsheetApp.getUi().createMenu('MatchLab').addItem('Refresh public research','matchLabRefresh').addItem('Enable 30-minute updates','matchLabInstall').addItem('Disable updates','matchLabDisable').addToUi();}
function matchLabInstall(){matchLabRefresh();matchLabDisable();ScriptApp.newTrigger('matchLabRefresh').timeBased().everyMinutes(30).create();mlStatus_('Enabled: 30-minute trigger; best-effort Google scheduling');}
function matchLabDisable(){ScriptApp.getProjectTriggers().filter(t=>t.getHandlerFunction()==='matchLabRefresh').forEach(t=>ScriptApp.deleteTrigger(t));mlStatus_('Disabled');}
function mlBook_(){const s=SpreadsheetApp.getActiveSpreadsheet();if(!s)throw Error('This script must be bound to the tracker spreadsheet.');return s;}
function mlStatus_(status){const s=mlBook_().getSheetByName('MatchLab Integration');if(s){s.getRange('B3').setValue(status);s.getRange('B4').setValue(new Date().toISOString());}}
function mlUrl_(base){if(typeof base!=='string'||!/^https:\/\/yshmyel\.github\.io\/matchlab-mobile\/$/.test(base))throw Error('Enter the verified HTTPS MatchLab Pages URL (trailing slash) in MatchLab Integration!B2.');return base;}
function mlFetch_(url){const r=UrlFetchApp.fetch(url,{muteHttpExceptions:true,followRedirects:false});if(r.getResponseCode()!==200)throw Error('Feed HTTP '+r.getResponseCode());const text=r.getContentText();if(text.length>5000000)throw Error('Feed unexpectedly large');const f=JSON.parse(text);if(f.schema_version!==1)throw Error('Unsupported schema');return f;}
function mlSafe_(v){if(v===null||v===undefined)return '';if(typeof v==='number')return Number.isFinite(v)?v:'';const s=String(v);return /^[=+@-]/.test(s)?"'"+s:s;}
function mlSheet_(name,headers){const b=mlBook_();const s=b.getSheetByName(name)||b.insertSheet(name);const existing=s.getRange(1,1,1,headers.length).getValues()[0];if(existing.some(Boolean)&&existing.some((v,i)=>v!==headers[i]))throw Error('Unexpected headers in '+name+'; refusing to overwrite');s.getRange(1,1,1,headers.length).setValues([headers]);s.setFrozenRows(1);return s;}
function mlResearchRows_(log){return log.predictions.map(p=>[p.key,p.generated_utc,p.league,p.league==='nba'?p.player:p.home+' vs '+p.away,p.market==='nplus'?p.threshold+'+ '+p.stat:'1H 1X2',p.selection,p.probability??p.probabilities?.[p.selection]??'',p.model_version,p.grade||'Pending',p.actual_value??p.actual??'',p.league==='nba'?'ESPN player logs; conditional on playing':'open-matchday reported HT; provisional model',log.updated_utc,p.status,'UNVERIFIED / blank price']);}
function matchLabRefresh(){const lock=LockService.getDocumentLock();if(!lock.tryLock(1000))return;try{
 const config=mlBook_().getSheetByName('MatchLab Integration');if(!config)throw Error('Missing MatchLab Integration configuration');const base=mlUrl_(config.getRange('B2').getValue());
 const log=mlFetch_(base+'data/prediction_log.json');const perf=mlFetch_(base+'data/performance.json');if(!Array.isArray(log.predictions)||!perf.soccer)throw Error('Malformed research feed');
 if(Date.now()-Date.parse(log.updated_utc)>7200000)throw Error('Research feed is stale; keeping existing rows');
 const s=mlSheet_('MatchLab Research',ML_RESEARCH_HEADERS);const old=s.getLastRow()>1?s.getRange(2,1,s.getLastRow()-1,ML_RESEARCH_HEADERS.length).getValues():[];
 const map=new Map(old.filter(r=>r[0]).map(r=>[r[0],r]));for(const row of mlResearchRows_(log))map.set(row[0],row.map(mlSafe_));const rows=Array.from(map.values());
 if(rows.length){if(s.getMaxRows()<rows.length+1)s.insertRowsAfter(s.getMaxRows(),rows.length+1-s.getMaxRows());s.getRange(2,1,rows.length,ML_RESEARCH_HEADERS.length).setValues(rows);}
 const per=mlSheet_('MatchLab Performance',ML_PERF_HEADERS);const out=[];
 for(const [league,m] of Object.entries(perf.soccer)){out.push([league,m.model||'HT unavailable',m.test?.n??0,m.test?.accuracy??'',m.test?.log_loss??'',m.test?.brier??'',m.baseline_test?.log_loss??'',m.status,perf.generated_utc]);}
 for(const p of perf.nba||[]){const m=p.backtest;out.push(['NBA '+p.player+' '+p.threshold+'+ '+p.stat,m.model||'Unavailable',m.test?.n??0,m.test?.accuracy??'',m.test?.log_loss??'',m.test?.brier??'','',m.status,perf.generated_utc]);}
 if(out.length){if(per.getMaxRows()<out.length+1)per.insertRowsAfter(per.getMaxRows(),out.length+1-per.getMaxRows());per.getRange(2,1,out.length,ML_PERF_HEADERS.length).setValues(out.map(r=>r.map(mlSafe_)));if(per.getLastRow()>out.length+1)per.getRange(out.length+2,1,per.getLastRow()-out.length-1,ML_PERF_HEADERS.length).clearContent();}
 mlStatus_('Last refresh succeeded; '+rows.length+' research snapshots. Trigger state unchanged.');
 }catch(e){mlStatus_('ERROR: '+e.message);throw e;}finally{lock.releaseLock();}}
