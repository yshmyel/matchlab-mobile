# MATCHLAB — CLAUDE CODE PROJECT HANDOFF

**Date:** November 7, 2026  
**Role:** Lead developer, data engineer, sports research systems maintainer

> **Provenance and status:** Sections 1–9 preserve the project handoff supplied by the user from the ChatGPT conversation “Open MatchLab App” (`6aee595e-0fc4-83e8-a59f-429150d4751f`). Historical changes, symptoms, scores, bankroll figures, and external automation schedules in those sections are **reported context**, not independently verified facts. Section 10 adds a repository audit against commit [`eee6237e6f96155ca36ace556d55bc7c15bce79d`](https://github.com/yshmyel/matchlab-mobile/commit/eee6237e6f96155ca36ace556d55bc7c15bce79d). Read it before interpreting the earlier claims as current behavior. This handoff adds documentation only; it does not change application code, Sheet contents, or automations.

## 1. Project resources

**Live desktop/mobile app:**  
https://yshmyel.github.io/matchlab-mobile/

**GitHub repository:**  
https://github.com/yshmyel/matchlab-mobile

**Google Sheets research database:**  
https://docs.google.com/spreadsheets/d/1N37U-4WuFkb5C1fgvyw-17AmhPZENaHxmESO1gYHGBA/edit

**Public picks data:**  
https://github.com/yshmyel/matchlab-mobile/blob/main/data/picks.json

You are resuming an existing project. Do not start from scratch.

Read the repository, GitHub Actions workflows, deployed application, spreadsheet tabs, formulas, and synchronization logic before editing anything.

The following information is a handoff of previously reported changes and outstanding requests. Verify actual implementation status against live sources rather than assuming every change was successfully deployed.

## 2. What ChatGPT has been working on

### Google Sheets research tracker

The Google Sheet is the primary research and historical grading database.

Recent reported updates:

- Added and tracked soccer first-half predictions, including Home, Draw, and Away.
- Recorded 35 soccer first-half research predictions for November 5 in a separate `FC 1H · Nov 5` tab.
- Added NBA, NHL, college basketball, and college football research and picks.
- Updated completed-game grades, distinguishing HIT, MISS, PASS, Pending, and cashed-out bets.
- Added and improved dashboard metrics, formulas, and visual organization.
- Hidden and marked older date-specific tabs red to preserve history while keeping the current day readable.
- Updated daily and hourly research/score-checking routines.
- Added a requirement to research live upset potential rather than relying only on pregame predictions.

Important: A research prediction is not automatically a placed wager. Preserve separate states for researched, recommended, placed, cashed out, settled, and graded.

**Known data issues:**

- The Dashboard has previously shown 0 picks while predictions existed in sport-specific tabs.
- A Dashboard `#REF!` formula issue was reportedly repaired, but remaining formulas need auditing.
- The Tracker's pick count and dashboard totals may disagree.
- The reported bankroll values of $203 and $232.63 are inconsistent. Reconcile using actual wager transactions, not assumptions.
- Some MatchLab grades are missing even though the Google Sheet contains completed results.

Do not delete historical records, rewrite past picks, reset bankroll information, or destroy formulas.

### MatchLab application

Reported application work includes:

- A mobile-friendly progressive web application.
- GitHub Pages hosting.
- ESPN-based game/score feeds.
- A scoreboard with sport selection.
- NBA research and soccer-first-half prediction views.
- Bet logging, result grading, history, and export/restore functionality.
- LIVE and FINAL indicators.
- Improvements intended to keep today's picks visible across tab switches.
- Separate tab filters so filters do not incorrectly carry between sports.
- One-minute in-app ESPN score polling.
- Scheduled GitHub Actions feed generation and deployment.
- Initial integration work with the Google Sheet.

Some of these changes may exist only in the repository or a development session rather than the deployed site. Test everything.

## 3. Current problems requiring investigation

### Critical: Feed freshness and missing games

We previously observed:

- MatchLab displaying 0 loaded games and a Demo / Offline status.
- A November 7 date rollover that initially continued serving November 6 data.
- Seven NBA and twelve NHL fixtures missing from an earlier feed.
- A static feed refreshing later than its intended 30-minute schedule.
- A GitHub Actions "Refresh and deploy MatchLab" workflow failure on November 6.
- Subsequent reports of restored fixture coverage, but without a complete end-to-end verification.

Investigate the entire pipeline:

ESPN/source API → ingestion → normalized data → JSON generation → repository → GitHub Actions → GitHub Pages → browser cache → MatchLab UI.

Check timezone handling in America/Los_Angeles, including games crossing midnight.

The application must display explicit freshness timestamps and errors rather than silently treating missing data as zero.

### Critical: Result grading

An audit reported 48 settled predictions lacking `grade_source` references.

One example: Minnesota NHL was still Pending in MatchLab even though its 4–1 final result had reportedly been verified and graded HIT in the spreadsheet.

Requirements:

- Automatically reconcile completed games.
- Obtain verifiable final results.
- Include source links and timestamps.
- Distinguish actual full-game results from halftime results.
- Do not grade PASS selections as wins.
- Record cashouts as their own settlement category.
- Prevent duplicate grading.
- Never treat missing results as losses.

### Critical: Google Sheet synchronization

Make the application and spreadsheet consistent without overwriting manually entered information.

Confirm which of these already works:

- Reading existing picks.
- Reading research-only predictions.
- Writing new validated predictions.
- Updating live scores.
- Synchronizing completed results.
- Synchronizing grades and cashouts.
- Updating dashboard totals and bankroll.

Use stable IDs and idempotent updates.

Keep credentials private. Do not expose private spreadsheet authentication in client-side code.

## 4. Research priorities

### Priority 1: Soccer

Soccer is currently the primary research focus.

Cover as many feasible matches across multiple leagues each day as reliable data allows.

For each game, research:

- Team strength and recent form.
- Home/away performance.
- Attack and defense quality.
- Starting lineup and important absences.
- Rest, rotation, and fixture congestion.
- First-half scoring patterns.
- Historical matchup context where useful.
- First-half Home / Draw / Away probabilities.
- Upset potential and uncertainty.

Do not require betting odds to create a research prediction. Odds are needed later to determine value, not to decide whether research can begin.

Previous estimates relied heavily on single-source Forebet information and were not proven to be calibrated MatchLab model outputs.

Build an auditable model using actual data, measure calibration, and backtest on completed fixtures.

### Priority 2: NBA

Research NBA games and player props in N+ format only.

Examples:

- 20+ Points
- 6+ Rebounds
- 4+ Assists

Do not substitute Over/Under prop recommendations for the preferred N+ format.

Emphasize:

- Confirmed rosters and injuries.
- Expected minutes.
- Matchup-specific defense.
- Opponent positional weaknesses.
- Recent role and opportunity.
- Rest and rotation.
- Statistical probabilities.

Do not select props simply because they have appealing odds.

### Priority 3: NHL

Track game winners, upset potential, and verified player props where supported.

Include confirmed starting goalies when available. Never invent goalie confirmations.

### Background coverage

Maintain college basketball, college football, and other previously tracked sports without letting them interfere with the primary soccer workflow.

## 5. Daily and live research automations

There are existing ChatGPT automation routines, separate from MatchLab's own GitHub Actions:

**Daily Multi-Sport Research**

- Daily at 6:30 AM Pacific.

**Hourly Multi-Sport Watch**

- Hourly at minute 20.
- Includes live scores, grading, soccer and other tracked sports.

**MatchLab Audit Watch**

- Hourly at minute 10.
- Designed to catch meaningful app/repository faults with low resource usage.

Do not assume these external routines can be replaced or modified from the repository.

Their current schedules were created outside Claude Code. Your task is to ensure the application and its data pipeline work correctly with their outputs.

Live match evaluation should identify:

- Unexpectedly strong underdog performances.
- Halftime draws and emerging upset opportunities.
- Material changes from the pregame assessment.
- Important player or lineup changes.
- Differences between predicted and actual game development.

Never fabricate a live update when a reliable source is unavailable.

## 6. Specific November 6–7 records to reconcile

Previously reported results include:

- SMU ML — HIT, 51–28.
- Buffalo ML — HIT, 5–2.
- Minnesota ML — HIT, 4–1.
- Nebraska ML — MISS, 13–24.
- New Mexico ML — HIT, 31–3.
- TCU–Arizona Under 46.5 — MISS.
- East Carolina — PASS.
- Anaheim upset selection — PASS.

Check sport, event date, opponent, exact market, and official scores before synchronizing any of these.

The public picks file previously included examples of:

- Tyrese Maxey 20+ Points.
- James Harden 4+ Assists.
- Shai Gilgeous-Alexander 20+ Points.
- Buffalo ML.
- Minnesota ML.
- An NHL PASS card.

These are historical examples, not current betting recommendations.

## 7. Desktop experience

The user now wants to use MatchLab on a PC as well as an iPhone.

Preserve the mobile experience while developing a genuinely useful responsive desktop layout.

Desktop requirements:

- Full scoreboard and research dashboard.
- Clear daily picks across all supported sports.
- LIVE / FINAL / UPCOMING indicators.
- Search and filtering that preserve state correctly.
- Historical picks and graded outcomes.
- Heatmaps showing performance by sport, market, and time period.
- A manual bet-entry workflow where the user can record actual wagers.
- Cashouts, stakes, returns, and bankroll history.
- Performance statistics based only on verified historical outcomes.

Show research predictions, verified edges, and actual placed bets as separate concepts.

The user wants an interface that is easy to read, not a crowded spreadsheet reproduced inside a browser.

## 8. Development rules

1. Preserve existing code, spreadsheet formulas, historical data, and working functionality.
2. Audit before modifying.
3. Use source-backed data and never fabricate odds, stats, predictions, or results.
4. Maintain explicit source, timestamp, and confidence metadata.
5. Use Pacific time for scheduling and display.
6. Handle partial API failure gracefully.
7. Test ingestion, midnight rollover, duplicate prevention, missing games, grading, and spreadsheet reconciliation.
8. Maintain a low-resource audit process.
9. Keep real-money betting execution disabled. This is a research and tracking application, not an automatic wagering bot.
10. Run tests before deploying and verify the public application after deployment.

## 9. Your immediate assignment

Begin with a read-only audit of the GitHub repository, deployed application, Google Sheet, and Actions history.

Produce a concise status report showing:

- What is actually implemented.
- What ChatGPT previously reported but cannot be verified.
- What is broken.
- Which data is stale or inconsistent.
- What is missing from the desktop app.
- Which features need the most urgent fixes.

Then repair the confirmed issues in priority order, beginning with feed freshness, missing fixtures, grading provenance, and spreadsheet synchronization.

Make changes directly to the existing project when access is available. Run tests, deploy successfully, and verify the deployed result.

At the end, report the exact files changed, tests run, workflow results, and the remaining limitations.

**Goal: One reliable MatchLab system, with the Google Sheet as the historical research and grading database, and the desktop/mobile application as the primary interface.**

## 10. Repository verification added November 7, 2026

### Evidence levels and boundaries

The repository was accessible with read and push permissions; its default branch was `main` at the audit commit linked above. Source inspection establishes implementation, not successful execution in the user's browser or private spreadsheet. No authenticated Sheet inspection, browser session, external automation inspection, or fresh live-source reconciliation was performed for this handoff.

| Area | Verified evidence | Still reported or unverified |
| --- | --- | --- |
| Hosting and refresh | Workflow, successful Actions logs, and deployed-feed smoke check described below | Current desktop/iPhone rendering and uninterrupted fixture coverage |
| Sheets | Bound Apps Script source and setup instructions | Actual tabs/formulas, seeding, authorization, installed triggers, dashboard repairs, bankroll |
| Grading | Source logic, existing helper tests, and archived grades | The reported 48 missing sources, named historical results, Sheet/app agreement |
| External routines | Names and schedules supplied in section 5 | Whether those routines are currently enabled or successfully publishing |
| Desktop | App views and private journal implementation/documentation | Full desktop acceptance, all requested heatmaps and bankroll reconciliation |

[`BUILD_STATUS.md`](../BUILD_STATUS.md) and [`integrations/SETUP.md`](../integrations/SETUP.md) contain earlier claims that three MatchLab tabs were seeded, 32 snapshots imported, and original tracker tabs preserved. Treat these as historical reports. BUILD_STATUS also reports private script installation with authorization/trigger checks pending. Neither document proves the current Sheet state; its old test/card counts are not the current baseline.

### Google Sheet integration: current direction and contract

Read [`integrations/MatchLab.gs`](../integrations/MatchLab.gs), [`integrations/appsscript.json`](../integrations/appsscript.json), and [setup](../integrations/SETUP.md) before touching the spreadsheet.

- The implemented connection is **public app feeds → private MatchLab Sheet tabs**. It does not read the original private tracker into the public app, reconcile its dashboard/bankroll, or synchronize private cashouts. The Sheet's role as the historical system of record is the user's target; it is not proof of complete two-way integration today.
- The bound script requires `MatchLab Integration!B2` to equal the allowlisted app URL, including its trailing slash. B3/B4 hold status and its UTC timestamp. The configuration tab must already exist.
- `matchLabRefresh` reads `data/prediction_log.json` and `data/performance.json`. It checks HTTP 200, schema version 1, disables redirects, caps response length, and rejects a prediction log more than two hours old. It uses a document lock and validates destination headers.
- Archive freshness is not result freshness: `grade_files` stamps `updated_utc` even without new successful grades or when grading errors occur. Verify individual event/result provenance as well as the archive timestamp.
- `MatchLab Research` A:N: Key; Generated UTC; Sport; Game / Player; Market; Selection; Probability; Model; Grade; Actual; Source / Context; Updated UTC; Status; Odds. Rows are upserted by Key while prior keyed rows remain.
- `MatchLab Performance` A:I: Sport / League; Model; Test n; Accuracy; Log loss; Brier; Baseline log loss; Status; As of. Performance rows are replaced on a nonempty update. Research odds are marked `UNVERIFIED`; no accepted ticket price is imported.
- `matchLabInstall` refreshes and installs a best-effort 30-minute trigger after removing matching refresh triggers in that project. `matchLabDisable` targets `matchLabRefresh` triggers. Google authorization is required. There is no public Apps Script web-app endpoint in this source.
- Source-level checks for the next audit: invalid/missing/future log timestamps can bypass the age comparison; performance freshness is unchecked; writes across tabs are not transactional; empty performance results retain old rows; the research formatter labels every non-`nplus` market as `1H 1X2`. Reproduce these cases safely before changing behavior or importing broader sports.

Keep credentials, private exports, actual wagers, and transaction evidence out of this public repository. The Sheet URL identifies the intended resource; it grants no spreadsheet access.

### Feed freshness, live behavior, and deployment

[`app.js`](../app.js) implements two refresh paths: published JSON every five minutes, plus direct ESPN score polling at startup, every visible-tab minute, and on visibility return. Only provider state `in` earns LIVE. The score merge protects against older timestamps and live/final state regression. The published latest-score feed warns above two hours; live-score freshness warns above 150 seconds. Shortlist and history freshness are not independently checked by that warning.

The live/final retention, separate-filter, and minute-score changes are present in the audited source. [Commit `203a7a2`](https://github.com/yshmyel/matchlab-mobile/commit/203a7a247715685f3cbb0cdeada6017be83f570e) installed those changes; its diff does not demonstrate a later regression. Browser acceptance remains required.

[`pages.yml`](../.github/workflows/pages.yml) runs on `main` pushes, manual dispatch, and `7,37 * * * *` (minutes 07 and 37 each hour UTC). It tests, builds Pacific today/yesterday data, archives `prediction_log.json` and `picks.json`, deploys selected public assets, and smoke-tests the published site. Schedules are best effort.

**Do not infer deployed staleness from tracked JSON alone.** The workflow generates `latest.json`, `performance.json`, and `yesterday.json` for the Pages artifact without committing those generated copies. Compare deployed feed timestamps, Pacific slate dates, workflow output, and browser cache separately. [`sw.js`](../sw.js) uses cache `matchlab-v6`, a network-first shell, and excludes `/data/` requests from its cache handling.

[Actions run `42364773849`](https://github.com/yshmyel/matchlab-mobile/actions/runs/42364773849) succeeded November 7 around 02:38 AM Pacific (10:38 UTC). Its logs show 32 Python tests and frontend/tracker/Sheets checks passing, 38 games, six soccer forecasts, 108 NBA model queries, no pipeline-reported errors, a 17-game prior-day build, Pages deployment, and a successful published-feed smoke check. These counts are different data categories, not editorial-pick totals. The smoke check establishes availability/schema/freshness at that run, not complete browser or Sheet behavior.

Reproduce these source-level concerns during the read-only audit:

1. Published builders emit partial-coverage `status/errors/counts`, but the UI refresh does not display those fields directly; check missing-league warnings.
2. Direct polling always includes NBA/NHL, but soccer recovery depends on existing current-day league entries, unless there are no current-day entries at all. Check recovery of an empty/missing soccer league.
3. Check Pacific midnight rollover, an open/sleeping browser, failed requests, and cache upgrades against exact expected ESPN event IDs.
4. A conditional workflow step uses `unzip -o matchlab-source.zip` and commits expanded files outside `.github`. It can overwrite source if a package is reintroduced. The audited run skipped this step; inspect any future archive and diff before using it.

### Grading and research publication

Read [`grading.py`](../grading.py), [`pipeline.py`](../pipeline.py), [`models.py`](../models.py), [`research.py`](../research.py), and [`tracker.js`](../tracker.js). Keep four datasets separate: editorial picks, model backtests, forward forecast grades, and actual placed-bet profit.

- `pipeline.py` archives the first eligible pregame model snapshot using stable keys and invokes `grade_files`. Completed-game summaries are fetched independently of today's player list. Inclusive N+ means `actual >= threshold`; unavailable results remain pending and reported DNP is distinct from a loss.
- The grading loop handles pending `nplus`, `ft`, and `1h` records. The outcome helper also recognizes legacy `n+`, but the loop does not dispatch it. The loop waits for full competition completion even for `1h`, and does not revisit already graded rows. Provenance backfill therefore needs a deliberate reconciliation path, rather than assuming an ordinary refresh repairs old grades.
- `data/picks.json` is an editorial input. Actions refreshes scores, grades, and deploys; it does **not** generate the daily researched shortlist. Research routines must publish validated picks while preserving original timestamps and prior selections. Never add a retrospective pregame pick.
- The inspected archive held 299 model forecasts (81 Win, 87 Loss, 131 Pending); the editorial file held six November 6 Pacific records (three Win, two Loss, one pass). These are snapshot observations, not independent confirmation of each outcome or evidence of profit.
- The existing device-local journal and manual research selections remain separate from public model snapshots. Placed tickets use browser local storage, manual settlements, and CSV/JSON transfer; they have no automatic grading or Sheet/cloud synchronization. Reimporting an existing ticket ID does not update its settlement. Preserve actual accepted prices, stakes, cashouts, and returned amounts; reference odds cannot substitute for accepted odds. Provisional model probabilities and retrospective metrics do not establish a verified betting edge.

Bounded local checks against the immutable audit commit passed: seven grading unit tests, the Sheets helper check (six assertions), and tracker helper check (18 assertions). Commands were `python -B -m unittest discover -s tests -p test_grading.py -v`, `node tests/test_sheets.cjs`, and `node tests/test_tracker.cjs`. These do not test live ESPN, Sheet authorization/triggers, dashboard formulas, end-to-end reconciliation, or browser layout.

### Desktop roadmap and the first Claude session

The existing app has Today, Scores, History, My bets, Models, and Settings views. Its source has per-view filters and retained live/final selections. [`README.md`](../README.md) describes a responsive desktop journal, 13-week profit heatmap, daily filters, sportsbook summaries, and private export/import; inspect [`index.html`](../index.html) and `tracker.js` and test these in the browser before rebuilding them. Export/import is not automatic cross-device synchronization.

Proceed in this order, with completion evidence for each step:

1. **Inventory:** Record the checkout/deployed revisions, latest workflow result, feed timestamps/slate dates, Sheet tab/header/formula map, trigger status, and available external research outputs. Mark inaccessible sources explicitly; do not infer their contents.
2. **Reconcile:** Use stable event/player/market IDs to reproduce missing fixtures and grades. Check every section 6 example against dated source results; audit the reported 48 missing `grade_source` entries and dashboard/bankroll discrepancies without overwriting history.
3. **Report:** Produce the status report requested in section 9, with evidence for each confirmed fault, a separate reported/unknown list, and a minimal repair order. Then implement confirmed fixes within the user's authorized scope, preserving working code and private formulas.
4. **Complete desktop requirements:** Validate existing PC/iPhone workflows first, then fill confirmed gaps in sport/market/time heatmaps, cashout and bankroll history, and research-versus-placed-bet presentation. Keep soccer first, NBA N+ second, and NHL third; broader sports are requested coverage, not proof of existing feed support.
5. **Verify:** Run the repository's Python and JavaScript checks, test rollover/partial failure/idempotent reconciliation, deploy through the existing workflow, and verify the resulting public site. Report exact changed files, test results, deployed revision, and unresolved limitations.

The three external ChatGPT routines in section 5, the Apps Script trigger, the five-minute published-feed fetch, the one-minute visible-tab score poll, and GitHub Actions are separate mechanisms. Verify each in its owning system. This documentation change neither creates nor changes any of them.
