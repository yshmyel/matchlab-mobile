# Kalshi pick tracking

Add a public, read-only Kalshi tracker to the existing MatchLab PWA and Python build. Keep sports predictions, grades, actual wagers, bankroll and the private Sheet unchanged.

An explicit watchlist links an editorial pick ID to a verified Kalshi ticker and YES/NO side. Confirmation records the exact event, period, player, threshold and settlement-rule equivalence. Store a fingerprint of the pick's market identity and reject changed selections. Never infer a link from a similar title or reuse full-game probabilities for first-half markets.

The public GET client reads modern dollar/fractional fields and current event/series fees. Each successful refresh appends a timestamped observation to a separate JSONL archive. API failures retain the last observation with a visible error; they never create a new observation or reset its timestamp. The current feed contains quotes, sampled historical extremes and hypothetical analyses. No order/account endpoints or credentials exist.

Use Decimal arithmetic and walk book depth for entry and immediate exit. Show estimated fees, breakeven, maximum loss, hypothetical exit profits and the mathematical winning binary settlement ceiling. Current fees are assumptions for future exits. Unknown fees suppress net-profit claims. Stale, closed, nonbinary, crossed/missing quotes and insufficient depth block entry assessment. An independent probability plus its source is optional for CLI expected-value scenarios; provisional MatchLab probabilities are never silently imported. Future peak price and probability of reaching a target remain unknown.

The Kalshi page uses the existing dark responsive design and reports actual snapshot age in Pacific time. The existing Pages workflow runs the tracker once per existing refresh and persists its separate archive. No new scheduler or recurring job is started. Initial watchlist is empty until real contracts are confirmed; the product displays unlinked picks honestly.

Validation: deterministic Python tests for prices, depth, fees, stale/unsupported contracts, persistence and failures; JS tests for escaped rendering and freshness; existing repository checks; a bounded public API smoke test. Deliver on a feature branch and PR; do not merge or deploy automatically.
