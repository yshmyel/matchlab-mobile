# Kalshi research tracker

MatchLab can link an editorial pick to a confirmed Kalshi YES/NO contract, retain public price observations, and show hypothetical profit/loss after estimated fees. It never places orders, connects an account, changes sports grades or writes private wager/Sheet data.

## Confirm a contract

Use a current market ticker from Kalshi. Candidate discovery is bounded to one page of a specified series; a name resemblance does not confirm a match.

```powershell
python kalshi_bot.py search --series KXNBAGAME --query "team name" --limit 100
python kalshi_bot.py inspect EXACT-MARKET-TICKER
python kalshi_bot.py link EXISTING-PICK-ID EXACT-MARKET-TICKER --side yes --confirm-match "Confirmed the same event, full-game period, selected team and settlement rules"
python kalshi_bot.py refresh
```

Replace the example identifiers with actual values. Inspect `data/picks.json` for editorial IDs. For player milestones confirm the player and inclusive N+ threshold, not just a similar label. First-half soccer research requires an exact first-half contract. Confirm the YES/NO outcome and all settlement exceptions (draws, overtime, cancellation, participation). The confirmation is an explicit assertion by the person doing the match; the tool cannot prove equivalence from free text. Existing links cannot silently be reassigned. Changed pick identities are blocked for reconfirmation.

The initial watchlist is empty on purpose: no real contract was supplied with the request. Existing non-PASS picks appear as unlinked, including historical picks. Linking one later does not reconstruct its earlier executable quotes or establish that a hypothetical trade was placed.

## Assess a market when asked

```powershell
python kalshi_bot.py assess EXACT-MARKET-TICKER --side yes --budget 25 --target 0.70 --target 0.85
```

This performs fresh public reads and outputs JSON containing depth-weighted entry cost, estimated fees, maximum loss, immediate-exit value, a hypothetical break-even price, and target-price profit scenarios. `--contracts 10` can replace `--budget 25`; budget sizing uses whole contracts and includes estimated fees. Assessment alone does not add a watchlist link or claim an actual trade.

Expected-value scenarios additionally require an independent probability and its provenance or explicit assumption:

```powershell
python kalshi_bot.py assess EXACT-MARKET-TICKER --side no --contracts 10 --probability 0.65 --probability-source "Hypothetical user assumption, not a calibrated forecast" --target 0.75
```

The probability is for the selected side's final winning outcome. It does not describe the chance of touching a target price. No model probability is copied automatically from MatchLab, and supplied assumptions never establish a verified edge.

## History and refresh

- `data/kalshi_watchlist.json`: explicit public pick/contract links and selection fingerprints. Commit confirmed links through the normal PR flow.
- `data/kalshi_observations.jsonl`: separate append-only public observations. Created on the first linked successful refresh and retained across the existing Pages runs. No actual account balances or stakes belong here.
- `data/kalshi.json`: current derived feed. API failures retain previous observation times and add visible errors. Missing/bad local schemas abort rather than overwrite evidence.

The existing Pages workflow samples once at its existing minutes 07/37 schedule, which is best effort. No extra schedule, account key or service is installed. The browser fetches only MatchLab's published feed; its Refresh button cannot force a new exchange sample on GitHub Pages. The CLI provides an on-demand current analysis. Public API responses themselves can lag the exchange by seconds. A quote older than 120 seconds is marked a snapshot requiring refresh, so the scheduled dashboard is usually historical research, not a live execution screen.

Pages and the existing grader share a writer concurrency group and check out the latest main branch when they start. A failed publication retains the observation archive as a 30-day Actions artifact for recovery instead of silently discarding collected evidence. Other writers can still cause a rejected push; the job fails visibly rather than overwriting their edits.

The recorded high is the highest sampled bid since the contract was linked, with a sample count and start time. It is not a continuous all-time high, a prediction of the next high, or a guaranteed fill at the requested size. Historic candles/trades are not backfilled. A $1 winning settlement ceiling applies only to standard binary contracts; nonstandard payouts, unavailable fees, stale/closed markets and inadequate depth block entry assessment.

Fees use the current verified event override or series quadratic schedule, hypothetical taker execution, six-decimal trade-fee rounding, non-direct cent balance alignment and per-order rounding rebates. Book levels are modeled as fills. Actual fills, member precision, waivers, future fee changes and slippage may differ. Future scenario prices assume sufficient hypothetical exit liquidity; no likelihood is assigned to them. Break-even thresholds are mathematical estimates, not guaranteed valid order ticks.

## Verify

```powershell
python -m unittest discover -s tests -v
node tests/test_tracker.cjs
node tests/test_app.cjs
node tests/test_sheets.cjs
node tests/test_kalshi_ui.cjs
node tests/test_kalshi_app.cjs
```

Official API/fee sources and the reasoning behind these boundaries are recorded in [kalshi-api-research.md](kalshi-api-research.md).
