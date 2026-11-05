"""ESPN-reported full-game NBA reference odds. No prop/1H prices inferred."""
import math

def finite(value):
    if isinstance(value,bool):return None
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):return None

def price(value):
    n=finite(value)
    if n is None or not n.is_integer() or abs(n)<100:return None
    n=int(n)
    return {'american':n,'decimal':1+(n/100 if n>0 else 100/abs(n)),'implied_probability':100/(n+100) if n>0 else abs(n)/(abs(n)+100)}

def normalize_odds(summary,observed_utc,source_url):
    result=[]
    candidates=summary.get('pickcenter') or summary.get('odds') or []
    if not isinstance(candidates,list):return []
    for raw in candidates:
        if not isinstance(raw,dict):continue
        book=(raw.get('provider') or {}).get('name')
        if not isinstance(book,str) or not book.strip():continue
        markets={}
        home=raw.get('homeTeamOdds') or {};away=raw.get('awayTeamOdds') or {}
        ml={k:v for k,v in [('home',price(home.get('moneyLine'))),('away',price(away.get('moneyLine')))] if v}
        if ml:markets['moneyline']=ml
        spread=raw.get('pointSpread') or {};lines={}
        for side,legacy in [('home',home),('away',away)]:
            entry=((spread.get(side) or {}).get('close') or {});line=finite(entry.get('line'));p=price(entry.get('odds',legacy.get('spreadOdds')))
            if line is not None and p:lines[side]=dict(p,line=line)
        if lines:markets['spread']=lines
        total=finite(raw.get('overUnder'));totals={}
        if total is not None and total>0:
            for side,key in [('over','overOdds'),('under','underOdds')]:
                p=price(raw.get(key))
                if p:totals[side]=dict(p,line=total)
        if totals:markets['total']=totals
        if markets:result.append({'bookmaker':book.strip(),'source':'ESPN unofficial summary','source_url':source_url,'observed_utc':observed_utc,'source_quote_utc':None,'period':'full_game','markets':markets,'status':'REFERENCE SNAPSHOT','caveat':'ESPN does not supply a quote timestamp here. Observed time is our retrieval time. Availability and accepted prices must be checked at your sportsbook. These prices do not apply to 1H or player N+ markets.'})
    return result
