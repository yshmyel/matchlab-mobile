# MatchLab Mobile

Phone-friendly soccer first-half and NBA research app. Standard-library Python importer and buildless PWA; no API keys or paid dependencies.

## Current features

- Nine ESPN league scoreboards: NBA, Premier League, La Liga, Bundesliga, Serie A, Ligue 1 and UEFA Champions, Europa and Conference leagues.
- Soccer home/draw/away first-half outcomes only after a reported first half is complete and both period scores exist. Missing scores remain unknown.
- NBA records, individual period scores, game state, score and source links.
- Device-local pregame research selections, automatic Win/Loss/Pending grading, export and restore. NBA uses full-game winner; soccer uses 1H three-way result. This is a research log, not a betting ledger.
- Pacific date filter; displayed tipoff/kickoff times follow the device timezone.
- Current and prior-day feeds, stale/partial coverage notices, offline app shell.

## Deploy

See DEPLOY.md. The single GitHub Actions workflow refreshes public data and deploys on every main push, manual run and at minutes 7 and 37 each hour. GitHub schedules are best effort and may be delayed or disabled by inactivity. The app checks its published feed every five minutes while open.

Only web assets and public research feeds enter the Pages artifact. Local log data is never uploaded. No credentials are required by the workflow beyond the automatic short-lived GitHub token.

## Develop and verify

```
python -m unittest discover -s tests -v
node --check app.js
python pipeline.py
```

`verify_deployment.py SITE_URL` smoke-tests the deployed assets and current feed after deployment.

## Models and evaluation

ESPN's public endpoints are unofficial and can change. HT coverage depends on period scores returned by the source. Cached feeds cover today and yesterday, so older unsettled selections can require imported scoreboards. Postponed or canceled games remain pending; no sportsbook settlement rules are inferred. Restored entries are user-supplied, editable research records.

`pipeline.py` fits provisional first-half Poisson models with shrunk team rates and temperature calibration selected on an earlier validation block. It evaluates a later chronological test block and reports accuracy, log loss, Brier score, confidence bins and a league-frequency baseline. Entire fixture dates are excluded from their own training data. Domestic leagues currently have labels; UEFA competitions currently have none and stay WATCH. Exact canonical names or explicit aliases are required; unknown club mappings produce no forecast.

NBA N+ research uses Beta(1,1)-smoothed hit rates over 20 prior played games, with validation-selected temperature calibration and held-out tests. Minutes, opponent history and source-reported injuries are displayed as context, not fitted causal adjustments. Queries cover summary-listed points, assists and rebound leaders in today's NBA fixtures, capped at 24 players. The player selection introduces selection bias; results do not represent all NBA players or all thresholds. DNPs are excluded rather than silently treated as zero. The estimate is conditional on playing; new teams, roles and injuries may invalidate historical rates.

Public `performance.json` contains retrospective tests. `prediction_log.json` preserves first-generated pregame model snapshots, deduplicated by game/player/market/model. Completed matching source records grade the snapshots on later runs. Forward sample size starts at zero; retrospective tests are not forward results or profit. No verified odds, value-edge calculation, real bets or bankroll changes are implemented.

The bound Apps Script in `integrations/` pulls public research and performance into separate private MatchLab tabs in your existing tracker. No private tracker data is sent to the public app. Google authorization and script installation are required before unattended synchronization works. See `integrations/SETUP.md`.

Historical CSV importer retains attribution to Open Matchday (https://github.com/oladeeayo/open-matchday). Review upstream usage terms before commercial use.

## Reference odds

Available full-game NBA moneyline, spread and total prices are read from ESPN's summary pickcenter, with its reported bookmaker name, source link and our actual retrieval timestamp. ESPN's endpoint does not provide a quote timestamp, so these are reference snapshots, not a guarantee of current executable prices. Cached/old cards show a stale notice after 45 minutes. No full-game quote is assigned to a soccer 1H or NBA N+ market. Real's FanDuel integration has no verified public import API in this project; exact user-provided prices would need independent import and matching. No new betting edges are calculated.
