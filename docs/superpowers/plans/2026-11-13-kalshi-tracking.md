# Kalshi tracking implementation plan

**Goal:** Link researched picks to Kalshi contracts and retain auditable price observations and profit scenarios.

**Architecture:** A stdlib public GET client feeds Decimal analysis and a one-shot archive publisher. A separate PWA view renders the public feed. Existing research and wager stores remain unchanged.

**Tech stack:** Python 3.12 standard library, JSON/JSONL, buildless JavaScript, existing GitHub Pages workflow.

**Spec:** `docs/superpowers/specs/2026-11-13-kalshi-tracking-design.md`.

## Tasks

- [x] Client: `kalshi_api.py`, `tests/test_kalshi_api.py`. Verify exact ticker lookups, current fixed-point orderbooks, event fee overrides including zero, unsupported schedules, pagination and bounded retries. Public GET only; no credentials or browser requests.
- [x] Analysis: `kalshi_analysis.py`, `tests/test_kalshi_analysis.py`. First run failing tests for YES/NO depth and zero/missing quotes, fees, bid-versus-ask loss, unknown fees, stale/closed/nonbinary contracts, budget sizing, scenario/settlement distinctions, probability provenance. Implement `analyze(snapshot, contracts=10, budget=None, probability=None, probability_source=None, targets=None, now=None)` returning JSON-safe strings.
- [x] Bot: `kalshi_bot.py`, `tests/test_kalshi_bot.py`, separate watchlist/current feed/append-only archive. Test explicit pick links, selection fingerprints, repeated refreshes, archived high bid, partial failures preserving timestamps and historical source bytes. Provide `refresh`, `search`, `inspect`, `link` and `assess` CLI commands.
- [x] PWA: `kalshi_ui.js`, `tests/test_kalshi_ui.cjs`, `index.html`, `app.js`, `sw.js`. Add a Kalshi view, handle empty/unavailable/stale data without entry-ready claims and test escaping and official source links. Keep source quote refresh on the Python side.
- [x] Integration: extend existing Pages build and asset checks, preserve only separate tracking files, document commands and limitations in `docs/KALSHI.md` and README. Keep existing schedule intact.
- [x] Verify: run all Python/JS checks, smoke-test a bounded official public market lookup and inspect the UI at phone/desktop sizes. Independently review the final diff and fix material findings.

Delivery: commit/push the verified feature branch and open a PR without merging.
