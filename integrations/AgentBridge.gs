/** MatchLab agent bridge: GitHub Issues <-> Google Sheet. Add as a second file in the
 * same bound Apps Script project as MatchLab.gs.
 *
 *  Pull (always): comments on issues labelled `agent-bus` -> "Agent Log" tab, upserted by
 *  comment id, so ChatGPT and you can read every agent's findings in the Sheet.
 *  Push (optional): rows in "Agent Inbox" with a Message and an empty Status are posted as
 *  comments on the bus issue (or a new issue when To = NEW ISSUE). Needs Script Property
 *  GITHUB_AGENT_TOKEN: fine-grained token, this repository only, Issues: read and write.
 *  The token stays in Script Properties; it is never written to a cell or the repository.
 */
const AB_REPO='yshmyel/matchlab-mobile';
const AB_API='https://api.github.com/repos/'+AB_REPO;
const AB_LOG_HEADERS=['Key','Posted UTC','Agent','Kind','Issue','Issue title','Summary','URL','Synced UTC'];
const AB_INBOX_HEADERS=['Created','From','To','Subject','Message','Status','GitHub URL'];
const AB_AGENTS={claude:'@claude',gemini:'@gemini',codex:'@codex'};

function matchLabAgentInstall(){matchLabAgentSync();matchLabAgentDisable();ScriptApp.newTrigger('matchLabAgentSync').timeBased().everyMinutes(15).create();mlStatus_('Agent bridge enabled: 15-minute trigger');}
function matchLabAgentDisable(){ScriptApp.getProjectTriggers().filter(t=>t.getHandlerFunction()==='matchLabAgentSync').forEach(t=>ScriptApp.deleteTrigger(t));}

/** Who wrote a comment: explicit marker first, then the GitHub login. */
function abAgent_(body,login){const m=/<!--\s*agent:([a-z0-9_-]+)(?:\s+kind:([a-z0-9_-]+))?/i.exec(body||'');
 if(m)return {agent:m[1].toLowerCase(),kind:(m[2]||'note').toLowerCase()};
 const l=String(login||'').toLowerCase();
 const agent=l==='claude[bot]'?'claude':l.indexOf('gemini')>=0?'gemini':l.indexOf('chatgpt')>=0||l.indexOf('codex')>=0?'codex':l==='github-actions[bot]'?'checks':'user:'+l;
 return {agent:agent,kind:'note'};}
/** Plain-text one-paragraph summary for a cell. */
function abSummary_(body){return String(body||'').replace(/<!--[\s\S]*?-->/g,'').replace(/```[\s\S]*?```/g,'[code]').replace(/[#*_>`|]/g,'').replace(/\s+/g,' ').trim().slice(0,700);}
/** Comment body for an Inbox row; mentions route the message to the named agents. */
function abInboxBody_(row){const from=String(row[1]||'chatgpt').trim().toLowerCase().replace(/[^a-z0-9_-]/g,'')||'chatgpt';
 const to=String(row[2]||'').toLowerCase();const mentions=Object.keys(AB_AGENTS).filter(a=>to.indexOf(a)>=0||to.indexOf('all')>=0).map(a=>AB_AGENTS[a]);
 return '<!-- agent:'+from+' kind:message -->\n**From:** '+from+(row[3]?'  \n**Subject:** '+row[3]:'')+'\n\n'+String(row[4]).slice(0,6000)+(mentions.length?'\n\n'+mentions.join(' '):'');}
function abToken_(){try{return PropertiesService.getScriptProperties().getProperty('GITHUB_AGENT_TOKEN');}catch(e){return null;}}
function abGet_(url,token){const h={Accept:'application/vnd.github+json'};if(token)h.Authorization='Bearer '+token;
 const r=UrlFetchApp.fetch(url,{headers:h,muteHttpExceptions:true,followRedirects:false});if(r.getResponseCode()!==200)throw Error('GitHub HTTP '+r.getResponseCode());return JSON.parse(r.getContentText());}
function abPost_(url,token,payload){const r=UrlFetchApp.fetch(url,{method:'post',contentType:'application/json',payload:JSON.stringify(payload),headers:{Authorization:'Bearer '+token,Accept:'application/vnd.github+json'},muteHttpExceptions:true,followRedirects:false});
 if(r.getResponseCode()!==201)throw Error('GitHub post HTTP '+r.getResponseCode());return JSON.parse(r.getContentText());}
function abBusIssue_(token){const list=abGet_(AB_API+'/issues?labels=agent-bus&state=open&per_page=5',token);if(!list.length)throw Error('No open agent-bus issue');return list[0];}

function matchLabAgentSync(){const lock=LockService.getDocumentLock();if(!lock.tryLock(1000))return;try{
 const token=abToken_();let sent=0;
 // Push first, so this run's messages also appear in the log below.
 const inbox=mlSheet_('Agent Inbox',AB_INBOX_HEADERS);
 if(token&&inbox.getLastRow()>1){const range=inbox.getRange(2,1,inbox.getLastRow()-1,AB_INBOX_HEADERS.length);const rows=range.getValues();let bus=null;
  rows.forEach((row,i)=>{if(!String(row[4]||'').trim()||String(row[5]||'').trim())return;
   try{let res;if(String(row[2]).toUpperCase().indexOf('NEW ISSUE')>=0){res=abPost_(AB_API+'/issues',token,{title:String(row[3]||'Agent message').slice(0,200),body:abInboxBody_(row),labels:['agent-bus-msg']});}
    else{bus=bus||abBusIssue_(token);res=abPost_(AB_API+'/issues/'+bus.number+'/comments',token,{body:abInboxBody_(row)});}
    inbox.getRange(i+2,6,1,2).setValues([['SENT '+new Date().toISOString(),res.html_url]]);sent++;}
   catch(e){inbox.getRange(i+2,6).setValue('ERROR '+e.message);}});}
 // Pull: bus issue(s) plus message issues, all comments, upsert by comment id.
 const log=mlSheet_('Agent Log',AB_LOG_HEADERS);const old=log.getLastRow()>1?log.getRange(2,1,log.getLastRow()-1,AB_LOG_HEADERS.length).getValues():[];
 const map=new Map(old.filter(r=>r[0]).map(r=>[String(r[0]),r]));const now=new Date().toISOString();
 const issues=abGet_(AB_API+'/issues?labels=agent-bus&state=all&per_page=10',token).concat(abGet_(AB_API+'/issues?labels=agent-bus-msg&state=all&per_page=20',token));
 for(const issue of issues){const key='issue-'+issue.number;if(!map.has(key)){const who=abAgent_(issue.body,issue.user&&issue.user.login);map.set(key,[key,issue.created_at,who.agent,'issue','#'+issue.number,issue.title,abSummary_(issue.body),issue.html_url,now].map(mlSafe_));}
  for(let page=1;page<=5;page++){const cs=abGet_(AB_API+'/issues/'+issue.number+'/comments?per_page=100&page='+page,token);
   for(const c of cs){const who=abAgent_(c.body,c.user&&c.user.login);map.set('c-'+c.id,['c-'+c.id,c.created_at,who.agent,who.kind,'#'+issue.number,issue.title,abSummary_(c.body),c.html_url,now].map(mlSafe_));}
   if(cs.length<100)break;}}
 const rows=Array.from(map.values()).sort((a,b)=>String(b[1]).localeCompare(String(a[1])));
 if(rows.length){if(log.getMaxRows()<rows.length+1)log.insertRowsAfter(log.getMaxRows(),rows.length+1-log.getMaxRows());log.getRange(2,1,rows.length,AB_LOG_HEADERS.length).setValues(rows);}
 mlStatus_('Agent bridge OK: '+rows.length+' log rows, '+sent+' sent'+(token?'':' (read-only: no GITHUB_AGENT_TOKEN)'));
 }catch(e){mlStatus_('Agent bridge ERROR: '+e.message);throw e;}finally{lock.releaseLock();}}
