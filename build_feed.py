#!/usr/bin/env python3
"""Build a static, source-labelled feed for MatchLab. No bets or invented predictions."""
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from research import scoreboard, LEAGUES


def build(day, leagues, output):
    games=[]; errors={}; counts={}
    datetime.strptime(day, "%Y%m%d")
    for league in leagues:
        if league not in LEAGUES: raise ValueError(f'Unknown league: {league}')
        try:
            found=scoreboard(league, day)
            games.extend(found)
            counts[league]=len(found)
        except Exception as exc:
            errors[league]=str(exc)[:300]
    payload={
        'schema_version':1,
        'timezone':'America/Los_Angeles',
        'date':day,
        'generated_utc':datetime.now(timezone.utc).isoformat(),
        'source':'ESPN unofficial public scoreboard',
        'status':'partial' if errors else 'ok',
        'counts':counts,
        'errors':errors,
        'games':games,
        'predictions':[],
        'disclaimer':'Research only. No odds, picks or halftime probabilities are fabricated.'
    }
    if len(errors)==len(leagues):
        raise RuntimeError('All scoreboard sources failed; retaining previous feed: '+json.dumps(errors))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    return payload

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--date',default=datetime.now(__import__('zoneinfo').ZoneInfo('America/Los_Angeles')).strftime('%Y%m%d'))
    p.add_argument('--leagues',nargs='+',default=['nba','epl','la_liga','bundesliga','serie_a','ligue_1','ucl','uel','uecl'])
    p.add_argument('--output',default='data/latest.json')
    args=p.parse_args()
    if len(args.date)!=8 or not args.date.isdigit():p.error('Use YYYYMMDD')
    result=build(args.date,args.leagues,Path(args.output))
    print(json.dumps({'games':len(result['games']),'status':result['status'],'errors':result['errors']}))
