"""Fetch, validate, model and publish only public research data. No wagers or private tracker data."""
import argparse,csv,io,json,hashlib,time,os,re
from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor,as_completed
from research import get,scoreboard,LEAGUES,CSV_LEAGUES,OPEN_MATCHDAY
from models import canon,soccer_predict,soccer_backtest,nba_estimate,nba_backtest
ROOT=Path(__file__).parent;CACHE=ROOT/'.cache';DATA=ROOT/'data'

def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False));tmp.replace(path)

def cached(url,ttl=21600):
    CACHE.mkdir(exist_ok=True);p=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if p.exists() and time.time()-p.stat().st_mtime<ttl:return p.read_text()
    for attempt in range(3):
        try:
            s=get(url);p.write_text(s);return s
        except Exception:
            if attempt==2:raise
            time.sleep(1+attempt)

def history(league,season,cutoff):
    url=f'{OPEN_MATCHDAY}/{CSV_LEAGUES[league]}/results_{season}.csv';text=cached(url)
    rows=list(csv.DictReader(io.StringIO(text)));out=[];excluded=0;seen=set()
    for r in rows:
        try:
            h,a=int(r['ht_home']),int(r['ht_away']);day=datetime.strptime(r['date'],'%Y-%m-%d').strftime('%Y-%m-%d')
            if h<0 or a<0 or h>15 or a>15 or day>=cutoff:raise ValueError('Invalid or unavailable label')
            key=(day,canon(r['home']),canon(r['away']))
            if key in seen:continue
            seen.add(key);out.append({'date':day,'home':key[1],'away':key[2],'home_display':r['home'],'away_display':r['away'],'h':h,'a':a})
        except (KeyError,ValueError):excluded+=1
    return sorted(out,key=lambda r:r['date']),{'url':url,'sha256':hashlib.sha256(text.encode()).hexdigest(),'rows':len(rows),'labelled_before_cutoff':len(out),'excluded':excluded,'retrieved_utc':datetime.now(timezone.utc).isoformat()}

def nba_log(player,season):
    url=f'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{player}/gamelog?season={season}'
    raw=json.loads(cached(url));names=raw.get('names',[]);events=raw.get('events',{});out={}
    for typ in raw.get('seasonTypes',[]):
        # Evaluate regular season; exclude preseason, play-in and playoffs.
        label=typ.get('displayName','').lower()
        if 'regular season' not in label or 'play' in label:continue
        for cat in typ.get('categories',[]):
            for r in cat.get('events',[]):
                e=events.get(r.get('eventId'),{});vals=dict(zip(names,r.get('stats',[])))
                try:
                    date=datetime.fromisoformat(e['gameDate'].replace('Z','+00:00')).astimezone(timezone.utc).isoformat()
                    minute=str(vals.get('minutes',''));parts=minute.split(':');minutes=float(parts[0])+(float(parts[1])/60 if len(parts)>1 else 0)
                    if minutes<=0:continue
                    record={'id':r['eventId'],'date':date,'minutes':minutes,'opponent_id':e.get('opponent',{}).get('id'),'opponent':e.get('opponent',{}).get('displayName')}
                    for stat,name in [('rebounds','totalRebounds'),('assists','assists'),('points','points'),('threes','threePointFieldGoalsMade-threePointFieldGoalsAttempted')]:
                        v=str(vals.get(name,''));record[stat]=int(v.split('-')[0]) if re.fullmatch(r'\d+(?:-\d+)?',v) else None
                    out[record['id']]=record
                except (KeyError,ValueError):continue
    return list(out.values()),url

ALIASES={'acmilan':'milan','internazionale':'intermilan','fcinternazionalemilano':'intermilan','bayernmunich':'fcbayernmunchen','fcbarcelona':'barcelona','parissaintgermain':'parissaintgermain','manchesterunited':'manchesterunited'}
def mapped(name,rows):
    key=canon(name);known={r[x] for r in rows for x in ['home','away']}
    if key in known:return key
    # Explicit alias table only; no fuzzy matching to unknown clubs.
    key=ALIASES.get(key,key)
    matches=[v for v in known if ALIASES.get(v,v)==key]
    return matches[0] if len(matches)==1 else None

def main(day=None):
    now=datetime.now(timezone.utc);today=now.astimezone(ZoneInfo('America/Los_Angeles')).date();day=day or today.strftime('%Y%m%d');date=datetime.strptime(day,'%Y%m%d').date();iso=date.isoformat()
    season=f'{date.year%100:02}{(date.year+1)%100:02}' if date.month>=7 else f'{(date.year-1)%100:02}{date.year%100:02}'
    feed={'schema_version':1,'date':day,'generated_utc':now.isoformat(),'status':'ok','source':'ESPN unofficial; open-matchday','games':[],'errors':{},'counts':{},'predictions':[]}
    def board(k):return k,scoreboard(k,day)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for fut in as_completed([pool.submit(board,k) for k in LEAGUES]):
            try:k,g=fut.result();feed['games'].extend(g);feed['counts'][k]=len(g)
            except Exception as e:feed['errors'][str(len(feed['errors']))]=str(e)[:200]
    if not feed['counts']:raise RuntimeError('All sources failed; previous deployment must be retained')
    report={'schema_version':1,'generated_utc':now.isoformat(),'soccer':{},'nba':[],'sources':{},'errors':{},'disclaimer':'Provisional research baselines; no profitability or betting edge established. Backtests are retrospective and conditional on source accuracy.'}
    histories={}
    for league in CSV_LEAGUES:
        try:
            rows,provenance=history(league,season,(date+timedelta(days=1)).isoformat());histories[league]=rows
            report['sources'][league]=provenance;report['soccer'][league]=soccer_backtest([r for r in rows if r['date']<iso])
        except Exception as e:report['errors'][league]=str(e)[:200]
    # Join verified historical outcomes by exact canonical team/date keys only.
    for g in feed['games']:
        if g['league']=='nba':continue
        rows=histories.get(g['league'],[]);h=mapped(g['home']['name'],rows);a=mapped(g['away']['name'],rows)
        model=report['soccer'].get(g['league'],{})
        reason='Insufficient verified HT history' if model.get('status')=='unavailable' else 'Team mapping unavailable'
        if not h or not a or model.get('status')!='provisional':g['research']={'status':'WATCH','reason':reason};continue
        if g['state']!='pre' or datetime.fromisoformat(g['date_utc'].replace('Z','+00:00'))<=now:
            g['research']={'status':'WATCH','reason':'Pregame cutoff passed; no new prediction generated'};continue
        p=soccer_predict(rows,h,a,iso,model['shrink'],model['temperature'])
        if p and min(p['team_samples'].values())>=3:
            p.pop('baseline',None);p.update({'id':g['id'],'league':g['league'],'market':'1h','status':'PREDICTION / PROVISIONAL','generated_utc':now.isoformat(),'kickoff':g['date_utc'],'model_version':'ht-poisson-shrink-v1','odds':None,'edge':None,'risk':'HIGH' if max(p['probabilities'].values())<.55 else 'MODERATE','selection':max(p['probabilities'],key=p['probabilities'].get)})
            g['research']=p;feed['predictions'].append(p)
        else:g['research']={'status':'WATCH','reason':'Fewer than 3 prior matches for a team'}
    # Current scoreboards may omit HT scores. Keep unknown rather than deriving from incomplete goal lists.
    nba_actuals={};nba_cards=[];players={};injuries={};nba_games=[g for g in feed['games'] if g['league']=='nba']
    for game in nba_games:
        try:
            summary=json.loads(cached(game['detail_url'],ttl=1800))
            for t in summary.get('injuries',[]):
                for injury in t.get('injuries',[]):injuries[str(injury.get('athlete',{}).get('id'))]={'status':injury.get('status'),'updated':injury.get('date')}
            for t in summary.get('leaders',[]):
                for category in t.get('leaders',[]):
                    for leader in category.get('leaders',[])[:1]:
                        athlete=leader.get('athlete',{});pid=str(athlete.get('id',''))
                        if pid and pid not in players:players[pid]={'name':athlete.get('displayName'),'team':t.get('team',{}).get('id'),'game_id':game['id'],'game_date':game['date_utc'],'state':game['state'],'home_id':game['home']['id'],'away_id':game['away']['id']}
        except Exception as e:report['errors']['nba_summary_'+game['id']]=str(e)[:200]
    endyear=date.year+1 if date.month>=7 else date.year
    for pid,player in list(players.items())[:24]:
        try:
            rows=[];urls=[]
            for year in [endyear-1,endyear]:
                part,url=nba_log(pid,year);rows.extend(part);urls.append(url)
            rows=sorted({r['id']:r for r in rows if r['date']<now.isoformat()}.values(),key=lambda r:r['date'])
            nba_actuals[pid]=rows
            for stat,n in [('rebounds',6),('threes',3),('assists',4),('points',20)]:
                m=nba_backtest(rows,stat,n);report['nba'].append({'player':player['name'],'player_id':pid,'stat':stat,'threshold':n,'backtest':m})
                est=nba_estimate(rows,stat,n,player['game_date'],m.get('temperature',1))
                if not est:continue
                opponent=player['away_id'] if player['team']==player['home_id'] else player['home_id'];opp=[r for r in rows if r['opponent_id']==opponent and r.get(stat) is not None]
                status=injuries.get(pid,{'status':'Not listed in fetched report; availability unconfirmed','updated':None})
                pre=player['state']=='pre' and player['game_date']>now.isoformat()
                nba_cards.append(dict(est,player=player['name'],player_id=pid,game_id=player['game_id'],game_date=player['game_date'],stat=stat,threshold=n,injury=status,
                    opponent_sample=len(opp),opponent_hits=sum(r[stat]>=n for r in opp),status='RESEARCH / PROVISIONAL' if pre else 'WATCH / GAME STARTED',model_version='nba-beta-binomial-v1',backtest_n=m.get('test',{}).get('n',0),source_urls=urls,generated_utc=now.isoformat(),odds=None,edge=None,
                    caveat='Conditional on playing. Minutes, injury and opponent context shown, not causally adjusted. Thresholds are research queries, not bookmaker lines.'))
        except Exception as e:report['errors']['player_'+pid]=str(e)[:200]
    feed['nba_props']=nba_cards;feed['model_summary']={'soccer_leagues':len(report['soccer']),'nba_players':len(players)}
    if feed['errors']:feed['status']='partial'
    atomic(DATA/'latest.json',feed);atomic(DATA/'performance.json',report)
    archive_predictions(feed,now,histories,nba_actuals)
    print(json.dumps({'games':len(feed['games']),'soccer_predictions':len(feed['predictions']),'nba_research_queries':len(nba_cards),'errors':report['errors']}))
    return feed,report

def archive_predictions(feed,now,histories,nba_actuals):
    path=DATA/'prediction_log.json';old=json.loads(path.read_text()) if path.exists() else {'schema_version':1,'predictions':[]}
    rows=old['predictions'];keys={r['key'] for r in rows}
    for p in feed['predictions']:
        key=f"{p['league']}:{p['id']}:1h:{p['model_version']}"
        game=next(g for g in feed['games'] if g['id']==p['id'] and g['league']==p['league'])
        if key not in keys:rows.append(dict(p,key=key,grade='Pending',home=game['home']['name'],away=game['away']['name']));keys.add(key)
    for p in feed['nba_props']:
        if p['status']!='RESEARCH / PROVISIONAL':continue
        key=f"nba:{p['game_id']}:{p['player_id']}:{p['stat']}:{p['threshold']}:{p['model_version']}"
        if key not in keys:rows.append(dict(p,key=key,league='nba',market='nplus',selection='hit',grade='Pending'));keys.add(key)
    for r in rows:
        if r.get('actual') is not None:continue
        if r['league']=='nba':
            actual=next((x for x in nba_actuals.get(r['player_id'],[]) if x['id']==r['game_id']),None)
            if actual and actual.get(r['stat']) is not None:
                r['actual_value']=actual[r['stat']];r['actual']=int(r['actual_value']>=r['threshold']);r['grade']='Win' if r['actual'] else 'Loss';r['graded_utc']=now.isoformat()
        else:
            history_rows=histories.get(r['league'],[]);h=mapped(r.get('home',''),history_rows);a=mapped(r.get('away',''),history_rows)
            # Dates are source-local fixture dates. Exact mapping only, no fuzzy joins.
            day=r['kickoff'][:10];actual=next((x for x in history_rows if x['date']==day and x['home']==h and x['away']==a),None)
            if actual:
                r['actual']=['home','draw','away'][__import__('models').outcome(actual['h'],actual['a'])];r['grade']='Win' if r['selection']==r['actual'] else 'Loss';r['graded_utc']=now.isoformat();r['grade_source']='open-matchday reported HT score'
    soccer=[r for r in rows if r['league']!='nba' and r.get('actual') is not None]
    nba=[r for r in rows if r['league']=='nba' and r.get('actual') is not None]
    old['forward_metrics']={'soccer':__import__('models').metrics([(list(r['probabilities'].values()),['home','draw','away'].index(r['actual'])) for r in soccer]),'nba':__import__('models').metrics([([1-r['probability'],r['probability']],r['actual']) for r in nba])}
    old['updated_utc']=now.isoformat();atomic(path,old)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--date');a=p.parse_args();main(a.date)
