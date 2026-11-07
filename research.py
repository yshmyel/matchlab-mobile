#!/usr/bin/env python3
"""Free read-only sports data ingestion. Standard library only."""
import argparse,csv,io,json,time,urllib.request,urllib.parse
from datetime import datetime,timezone
from pathlib import Path

ESPN='https://site.api.espn.com/apis/site/v2/sports'
LEAGUES={'nba':('basketball','nba'),'nhl':('hockey','nhl'),'epl':('soccer','eng.1'),'la_liga':('soccer','esp.1'),'bundesliga':('soccer','ger.1'),'serie_a':('soccer','ita.1'),'ligue_1':('soccer','fra.1'),'ucl':('soccer','uefa.champions'),'uel':('soccer','uefa.europa'),'uecl':('soccer','uefa.europa.conf')}
OPEN_MATCHDAY='https://raw.githubusercontent.com/oladeeayo/open-matchday/master/data'
CSV_LEAGUES={'epl':'ENG_1_premier-league','la_liga':'ESP_1_la-liga','bundesliga':'GER_1_bundesliga','serie_a':'ITA_1_serie-a','ligue_1':'FRA_1_ligue-1','ucl':'UEFA_1_champions-league','uel':'UEFA_1_europa-league','uecl':'UEFA_1_conference-league'}

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'PersonalSportsResearch/0.1 (noncommercial)','Accept':'application/json,text/csv'})
    with urllib.request.urlopen(req,timeout=20) as resp: return resp.read().decode('utf-8-sig')

def number(value):
    try:
        n=float(value)
        return int(n) if n.is_integer() else None
    except (TypeError, ValueError): return None


def normalize_event(e, league):
    sport,slug=LEAGUES[league]
    c=(e.get('competitions') or [{}])[0]
    teams={x.get('homeAway'):x for x in c.get('competitors',[])}
    status=e.get('status') or c.get('status') or {}
    def team(side):
        v=teams.get(side,{})
        lines=v.get('linescores') or []
        return {'id':v.get('team',{}).get('id'),
                'name':v.get('team',{}).get('displayName'),
                'score':number(v.get('score')) if status.get('type',{}).get('state')!='pre' else None,
                'period_scores':[number(x.get('value')) for x in lines],
                'records':[str(x.get('name') or x.get('type') or 'Record')+': '+x['summary'] for x in v.get('records',[]) if x.get('summary')]}
    home,away=team('home'),team('away')
    settled=bool(status.get('type',{}).get('completed'))
    ht_ready=sport=='soccer' and (settled or (number(status.get('period')) or 0)>1 or status.get('type',{}).get('name')=='STATUS_HALFTIME')
    hs=home['period_scores']; aws=away['period_scores']
    ht={'home':hs[0], 'away':aws[0]} if ht_ready and hs and aws and hs[0] is not None and aws[0] is not None else None
    if ht: ht['result']='home' if ht['home']>ht['away'] else 'away' if ht['away']>ht['home'] else 'draw'
    return {'source':'ESPN (unofficial)','league':league,'id':e.get('id'),
            'date_utc':e.get('date'),'status':status.get('type',{}).get('name'),
            'state':status.get('type',{}).get('state'),'completed':settled,
            'clock':status.get('displayClock'),'period':status.get('period'),
            'home':home,'away':away,'halftime':ht,
            'source_url':f'https://www.espn.com/{league if league in ("nba","nhl") else "soccer"}/game/_/gameId/{e.get("id")}',
            'detail_url':f'{ESPN}/{sport}/{slug}/summary?event={e.get("id")}'}


def scoreboard(league,day):
    sport,slug=LEAGUES[league]
    url=f'{ESPN}/{sport}/{slug}/scoreboard?'+urllib.parse.urlencode({'dates':day,'limit':200})
    raw=json.loads(get(url))
    if not isinstance(raw.get('events'),list): raise ValueError('Missing events array')
    return [normalize_event(e,league) for e in raw['events']]

def historical(league,season):
    folder=CSV_LEAGUES[league];url=f'{OPEN_MATCHDAY}/{folder}/results_{season}.csv'
    rows=list(csv.DictReader(io.StringIO(get(url))))
    # Never convert missing HT into 0-0; missing is not a result.
    for r in rows:
        r['ht_usable']=bool(r.get('ht_home','').strip() and r.get('ht_away','').strip())
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--date',default=datetime.now(timezone.utc).strftime('%Y%m%d'));p.add_argument('--season',default='2627');p.add_argument('--out',default='output');p.add_argument('--leagues',nargs='+',default=['nba','epl','ucl','uel','uecl']);args=p.parse_args()
    if len(args.date)!=8 or not args.date.isdigit():p.error('date must be YYYYMMDD')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    report={'date':args.date,'created_utc':datetime.now(timezone.utc).isoformat(),'sources':{},'errors':{}}
    for league in args.leagues:
        if league not in LEAGUES:p.error('Unknown league: '+league)
        try:
            events=scoreboard(league,args.date)
            (out/f'{league}_{args.date}_scoreboard.json').write_text(json.dumps(events,indent=2,ensure_ascii=False))
            report['sources'][league]={'scoreboard_events':len(events)}
        except Exception as exc:report['errors'][league+'_espn']=str(exc)
        if league in CSV_LEAGUES:
            try:
                rows=historical(league,args.season)
                with (out/f'{league}_{args.season}_history.csv').open('w',newline='') as f:
                    if rows:
                        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
                report['sources'].setdefault(league,{})['historical_rows']=len(rows)
                report['sources'][league]['verified_ht_rows']=sum(x['ht_usable'] for x in rows)
            except Exception as exc:report['errors'][league+'_history']=str(exc)
        time.sleep(.3)
    (out/'run_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
