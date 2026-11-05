# MatchLab build verification

## Verified locally

- Live ESPN fetch: 37 current-day games, no league errors.
- Source-reported first-half training labels: 452 matches in five domestic leagues.
- Chronological validation/test, calibration selection, baseline comparison and missing-data gates.
- NBA player logs: 32 tested player/threshold combinations, source-reported minutes, opponent context and injury reports.
- 18 Python tests plus frontend grading and secure-sheet helper checks.
- Browser: model performance table and 32 NBA query cards render, no app-origin JavaScript errors observed.
- Authenticated Sheets: three new MatchLab tabs created and 32 research snapshots plus evaluation rows imported; original tracker not edited.

## Deployment

GitHub repository created: https://github.com/yshmyel/matchlab-mobile
Pages and Actions deployment verification are in progress. Do not treat this file as proof of a live deployment.

## Remaining limits

UEFA first-half labels unavailable; no forecasts for today's UEFA slate. All fitted models remain provisional; small retrospective test samples and no proven betting edge. No bookmaker odds, bets or profit claims. Scheduled private Sheets sync requires bound Apps Script installation and Google authorization. iPhone Home Screen installation must be completed on the user's device.
