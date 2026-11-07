# MatchLab multi-agent protocol

Read this before acting. It applies to every agent: Claude, Gemini, ChatGPT/Codex,
the deterministic checks, and the user. Project background is in
[docs/CLAUDE_HANDOFF.md](docs/CLAUDE_HANDOFF.md).

## Shared channel

| Where | What | Who writes | Who reads |
|---|---|---|---|
| GitHub issue labelled **`agent-bus`** (pinned "MatchLab Agent Bus") | Every finding, audit, grading notice and agent-to-agent message, as comments | All agents | All agents; mirrored to the Sheet |
| Other issues and PRs | One task each; label `agent:claude` or comment `@claude` / `@gemini` / `@codex` to assign | User, agents, Sheet Inbox | All |
| Google Sheet tab **Agent Log** | Read-only mirror of every bus comment (agent, kind, summary, link), refreshed every 15 min by `integrations/AgentBridge.gs` | Apps Script only | ChatGPT routines, user |
| Google Sheet tab **Agent Inbox** | Messages from ChatGPT or the user. Columns: Created, From, To, Subject, Message; leave Status blank. The bridge posts each row to the bus and fills Status + GitHub URL | ChatGPT, user | Bridge |

Every comment begins with a marker so the Sheet and other agents can tell authors apart:

```
<!-- agent:NAME kind:KIND -->
```

NAME is `claude`, `gemini`, `codex`, `chatgpt`, `checks` or `user`. KIND is `finding`, `audit`,
`grading`, `review`, `final-review`, `fix`, `message` or `status`.

## Roles and permissions

| Agent | Runs in | May | May not |
|---|---|---|---|
| **Checks** (`scripts/agent_audit.py`) | `agent-audit.yml`, every 2 h | Read the live feed, data and Actions runs; comment | Change anything |
| **Grading** (`scripts/grade_now.py`) | `grade.yml`, every 30 min | Commit `data/picks.json` and `data/prediction_log.json`, only when a grade changed | Touch any other file; regrade a graded row; turn a missing result into a loss |
| **Claude** | `claude.yml` on `@claude` / label `agent:claude` from the owner | Edit code on a `claude/*` branch and open a PR; comment | Push to main; rewrite history, past picks, bankroll or Sheet formulas |
| **Claude (audit)** | `agent-audit.yml` full report | Read and analyse; write a report file | Change files (read-only token) |
| **Gemini** | `gemini.yml`: every same-repo PR, `@gemini`, and last job of a full audit | Read the repo, public sources and the shared evidence bundle; return one Markdown report, which a separate job posts | Any write access. The review job has a read-only token, no persisted git credentials and read-only tools; only the `post` job can comment, and it never runs Gemini |
| **ChatGPT / Codex** | ChatGPT routines (Sheet) and Codex (`@codex` on PRs/issues when the Codex GitHub connector is enabled) | Read the bus/Agent Log; write to Agent Inbox; review PRs | Merge; enable betting |

**Gemini is the final reviewer.** In a full audit its job depends on every other job, so its
report is always the last comment. On PRs it reviews after Claude opens them. A PR with a
Gemini verdict of `BLOCK` must not be merged until the concern is resolved.

## Shared verified evidence

Every agent works from the same files, never from its own copy of the facts:

- `data/picks.json` (editorial shortlist) and `data/prediction_log.json` (automated model archive). They are different datasets; their sizes are expected to differ.
- `python scripts/reconcile.py --verify --json … --markdown …` (read-only): dataset accounting, duplicates, unsourced or PASS-graded rows, overdue Pending rows, and a live re-check of every settled grade against its cited ESPN source. Exit code 1 means duplicates, a graded PASS or a grade conflict.
- Gemini runs receive this bundle in `.agent/evidence/`, plus a dry-run of the grader. The bundle is attached to each run as an artifact.

Grades are written only by `grading.grade_files` (through `pipeline.py` and `scripts/grade_now.py`). It refuses any write that removes, duplicates or regrades a record, changes a selection, or converts a selection to PASS.

## Rules for every agent

1. Research and tracking only. Never place, automate or enable real-money bets.
2. Never print, commit or post passwords, API keys or tokens. Secrets live in GitHub
   Actions secrets or Apps Script Script Properties.
3. Never fabricate odds, stats, results, lineups or goalie confirmations. Cite a source URL
   (ESPN summary `https://site.api.espn.com/apis/site/v2/sports/<sport>/<league>/summary?event=<id>`)
   for every result or grade you assert.
4. Keep states separate: researched, recommended, placed, cashed out, settled, graded.
   PASS is never a win. Missing results stay Pending. A total landing exactly on the line is a Push.
5. Never delete or rewrite historical records, past picks, bankroll data or Sheet formulas.
   Corrections are new, sourced records or a PR with evidence.
6. Use Pacific time for slates and display.
7. Substantial changes go through a pull request with tests passing:
   `python -m unittest discover -s tests` and
   `node tests/test_tracker.cjs && node tests/test_app.cjs && node tests/test_sheets.cjs`.
8. State clearly where you agree or disagree with other agents and what you could not verify.

## How to ask for work

- Fix or build something: open an issue, include `@claude` (or add label `agent:claude`).
- Independent verification: comment `@gemini` on the issue or PR.
- Full audit (checks → Claude → Gemini last): add label `audit-request` to an issue, or run
  *Agent · Audit* manually from the Actions tab with `full` checked.
- From ChatGPT: append a row to the Sheet's **Agent Inbox** with To = `claude`, `gemini`,
  `all` or `NEW ISSUE`.
