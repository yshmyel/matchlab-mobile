"""Transparent, standard-library research baselines with chronological evaluation."""
import math, unicodedata
from collections import Counter

def canon(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s).lower() if c.isalnum())

def temperature(p,t):
    v=[max(x,1e-12)**(1/t) for x in p];return [x/sum(v) for x in v]

def metrics(samples):
    if not samples:return {'n':0}
    n=len(samples); bins=[]
    for k in range(10):
        b=[(p,y) for p,y in samples if min(int(max(p)*10),9)==k]
        if b: bins.append({'lower':k/10,'n':len(b),'confidence':sum(max(p) for p,y in b)/len(b),'accuracy':sum(p.index(max(p))==y for p,y in b)/len(b)})
    return {'n':n,'accuracy':sum(p.index(max(p))==y for p,y in samples)/n,
            'log_loss':-sum(math.log(max(p[y],1e-12)) for p,y in samples)/n,
            'brier':sum(sum((v-(i==y))**2 for i,v in enumerate(p)) for p,y in samples)/n,
            'ece':sum(b['n']/n*abs(b['confidence']-b['accuracy']) for b in bins),'calibration_bins':bins}

def outcome(h,a):return 0 if h>a else 2 if a>h else 1

def soccer_predict(rows,home,away,day,shrink=10,temp=1):
    past=[r for r in rows if r['date']<day]
    if len(past)<30:return None
    hm=sum(r['h'] for r in past)/len(past);am=sum(r['a'] for r in past)/len(past)
    def rate(team,scored,prior):
        games=[r for r in past if team in [r['home'],r['away']]][-20:]
        vals=[r['h'] if (r['home']==team)==scored else r['a'] for r in games]
        return (sum(vals)+shrink*prior)/(len(vals)+shrink),len(vals)
    avg=(hm+am)/2
    hs,hn=rate(home,True,avg);hc,_=rate(home,False,avg);aws,an=rate(away,True,avg);ac,_=rate(away,False,avg)
    # Geometric combination with league venue adjustment; shrink sparse teams.
    lh=max(.05,min(3.5,math.sqrt(hs*ac)*hm/max(avg,.05)))
    la=max(.05,min(3.5,math.sqrt(aws*hc)*am/max(avg,.05)))
    cells=[(h,a,math.exp(-lh-la)*lh**h/math.factorial(h)*la**a/math.factorial(a)) for h in range(13) for a in range(13)]
    total=sum(v for h,a,v in cells);p=[sum(v for h,a,v in cells if outcome(h,a)==k)/total for k in range(3)]
    p=temperature(p,temp)
    baseline=[(sum(outcome(r['h'],r['a'])==i for r in past)+1)/(len(past)+3) for i in range(3)]
    return {'probabilities':dict(zip(['home','draw','away'],p)),'raw_score_probabilities':{'0-0':math.exp(-lh-la),'1-1':math.exp(-lh-la)*lh*la},
            'expected_1h_goals':{'home':lh,'away':la},'team_samples':{'home':hn,'away':an},'training_n':len(past),'training_through':max(r['date'] for r in past),'baseline':baseline}

def soccer_backtest(rows):
    rows=sorted(rows,key=lambda r:r['date']);dates=sorted({r['date'] for r in rows})
    if len(rows)<60 or len(dates)<12:return {'status':'unavailable','reason':'Need 60 labelled matches and 12 distinct dates','n':len(rows)}
    cal=dates[int(len(dates)*.6)];test=dates[int(len(dates)*.8)]
    def samples(lo,hi,alpha,t):
        out=[];base=[]
        for r in rows:
            if not(lo<=r['date']<hi):continue
            x=soccer_predict(rows,r['home'],r['away'],r['date'],alpha,t)
            if x:
                y=outcome(r['h'],r['a']);out.append((list(x['probabilities'].values()),y));base.append((x['baseline'],y))
        return out,base
    best=None
    for alpha in [5,10,20]:
        for t in [.8,1,1.2,1.5]:
            s,_=samples(cal,test,alpha,t);m=metrics(s)
            if m['n'] and (best is None or m['log_loss']<best[0]):best=(m['log_loss'],alpha,t,m)
    if best is None:return {'status':'unavailable','reason':'No validation observations'}
    _,alpha,t,valid=best;s,b=samples(test,'9999',alpha,t)
    return {'status':'provisional','model':'ht-poisson-shrink-v1','shrink':alpha,'temperature':t,'validation_start':cal,'test_start':test,'validation':valid,'test':metrics(s),'baseline_test':metrics(b),'labelled_n':len(rows),'method':'Date-grouped 60/20/20 split; past dates only; hyperparameters chosen on validation, fixed before test. Expanding training history.'}

def nba_estimate(rows,stat,threshold,day,temp=1):
    past=[r for r in rows if r['date']<day and isinstance(r.get(stat),(int,float)) and r.get('minutes',0)>0][-20:]
    if len(past)<10:return None
    hits=sum(r[stat]>=threshold for r in past);p=(hits+1)/(len(past)+2);p=temperature([1-p,p],temp)[1]
    n=len(past);ph=hits/n;den=1+3.8416/n;mid=(ph+1.9208/n)/den;rad=1.96*math.sqrt(ph*(1-ph)/n+.9604/n**2)/den
    return {'probability':p,'hits':hits,'sample':n,'empirical_hit_rate':ph,'wilson95':[max(0,mid-rad),min(1,mid+rad)],'avg_minutes_last5':sum(r['minutes'] for r in past[-5:])/len(past[-5:]),'avg_minutes_sample':sum(r['minutes'] for r in past)/n,'training_through':past[-1]['date']}

def nba_backtest(rows,stat,threshold):
    dates=sorted({r['date'] for r in rows})
    if len(dates)<30:return {'status':'unavailable','reason':'Need 30 played games','n':len(dates)}
    cal=dates[int(len(dates)*.6)];test=dates[int(len(dates)*.8)]
    def samples(lo,hi,t):
        out=[]
        for r in rows:
            if lo<=r['date']<hi and r.get(stat) is not None:
                p=nba_estimate(rows,stat,threshold,r['date'],t)
                if p:out.append(([1-p['probability'],p['probability']],int(r[stat]>=threshold)))
        return out
    valid=[(metrics(samples(cal,test,t)),t) for t in [.8,1,1.2,1.5]];valid=[x for x in valid if x[0]['n']]
    if not valid:return {'status':'unavailable','reason':'No validation observations'}
    m,t=min(valid,key=lambda x:x[0]['log_loss'])
    return {'status':'provisional','model':'nba-beta-binomial-v1','temperature':t,'validation_start':cal,'test_start':test,'validation':m,'test':metrics(samples(test,'9999',t)),'method':'Played games only; last 20 prior games with Beta(1,1) smoothing. Date-grouped 60/20/20, temperature selected on validation.'}
