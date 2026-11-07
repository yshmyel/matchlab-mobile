"""Deployment smoke test; fails CI if published feed or assets are unavailable."""
import json, sys, time, urllib.request
from datetime import datetime, timezone
base=sys.argv[1].rstrip('/')+'/'
for attempt in range(6):
    try:
        for asset in ['','app.js','tracker.js','manifest.webmanifest','sw.js','research_ui.js','icons/apple-touch-icon.png','icons/icon-192.png','icons/icon-512.png','data/performance.json','data/prediction_log.json','data/latest.json','data/picks.json']:
            with urllib.request.urlopen(base+asset+'?check='+str(time.time()),timeout=20) as r:
                content=r.read()
                if asset=='data/latest.json':
                    f=json.loads(content)
                    assert f['schema_version']==1 and isinstance(f['games'],list)
                    age=(datetime.now(timezone.utc)-datetime.fromisoformat(f['generated_utc'])).total_seconds()
                    assert 0<=age<3600, 'Published feed stale'
        print('PASS: deployed assets and current feed'); break
    except Exception:
        if attempt==5: raise
        time.sleep(10)
