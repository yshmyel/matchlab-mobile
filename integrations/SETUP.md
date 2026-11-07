# Secure tracker integration

The existing tracker now has MatchLab Integration, MatchLab Research and MatchLab Performance tabs. They were seeded through the authenticated Google Sheets connection. Original tabs, formulas, balances and history were not edited.

## One-time activation

1. In the tracker choose Extensions → Apps Script. Keep the project bound to this spreadsheet.
2. Add MatchLab.gs from this folder. Set appsscript.json to the supplied manifest (enable manifest display in Project Settings).
3. Set MatchLab Integration!B2 to the verified HTTPS app URL, including the trailing slash.
4. Run matchLabInstall. Google requests permission for this spreadsheet, external public feed reads and installing the time trigger. Review and authorize under your own account.
5. Verify the integration status cell and trigger list. Check the MatchLab Research and Performance tabs after a successful run.

The trigger pulls every 30 minutes, subject to Google's scheduling and quotas. It is not deployed as a public web app. No service-account keys, tokens, private exports, or public tracker sharing are needed. The source host is restricted to the expected MatchLab GitHub Pages URL. The script writes only its own named MatchLab tabs and validates their headers before updates. The public app never receives private sheet data. Device-local manual selections are separate from model-generated snapshots.

## Update to the reconciliation release (re-paste required)

Apps Script does not update from GitHub. After this release is merged, re-paste `MatchLab.gs` into the bound project and run **MatchLab → Refresh public research** once. Then:

- **MatchLab Research** still mirrors `data/prediction_log.json`, the automated model archive (one row per player × N+ threshold and per soccer 1H forecast; 303 rows on Nov 7). Market labels now distinguish 1H, N+, full-game moneyline and totals. The Odds column reads `RESEARCH ONLY · no verified price` unless a verified sportsbook price exists.
- **MatchLab Picks** (new) mirrors `data/picks.json`, the editorial shortlist, including PASS cards with their official result. Before this release editorial picks never reached the Sheet automatically.
- Rows are upserted by stable key. A settled row (Win, Loss, Push, DNP, Not applicable) is never overwritten by an older Pending copy, and duplicate keys collapse to one row.
- The sync refuses feeds whose timestamp is missing, unparseable, more than 5 minutes in the future or over 2 hours old. Previously an invalid timestamp passed as fresh.

These tabs remain separate from your Bets, Dashboard and day tabs. Wagers, cashouts and bankroll are never read or written.

## Optional: keep the public feed fresh

GitHub runs scheduled workflows on a best-effort basis and has been skipping most of the 30-minute runs (gaps of 3–7 hours observed Nov 5–7), which leaves the feed stale and makes this sync refuse to update. To let this trigger request a refresh when the feed is older than 40 minutes:

1. Re-paste the current `MatchLab.gs` into the bound Apps Script project.
2. On GitHub, create a fine-grained personal access token limited to `yshmyel/matchlab-mobile` with only **Actions: Read and write**. Give it an expiry date.
3. In Apps Script → Project Settings → Script Properties, add `GITHUB_DISPATCH_TOKEN` with the token value. Never put it in a sheet cell or the repository.

Without the property, nothing changes. Dispatch failures never block the sheet sync. Delete the property to turn it off.

Disable through MatchLab → Disable updates. This affects only this script's MatchLab refresh trigger. Real wagers, balances and original tracker grades remain outside this integration.

## Optional: agent bridge (GitHub Issues ↔ Sheet)

`AgentBridge.gs` mirrors every comment on the **MatchLab Agent Bus** issue into an **Agent Log**
tab and posts rows from an **Agent Inbox** tab to GitHub. See [AGENTS.md](../AGENTS.md).

1. In Extensions → Apps Script, add a file named `AgentBridge`, paste `integrations/AgentBridge.gs`,
   and re-paste `MatchLab.gs` (its menu gained the bridge items). Save.
2. Reading works without a token. To let the Inbox post messages, create a fine-grained token at
   https://github.com/settings/personal-access-tokens/new limited to `yshmyel/matchlab-mobile`
   with **Issues: Read and write** only, then add Script Property `GITHUB_AGENT_TOKEN`
   (Project Settings → Script Properties). Never paste it into a cell.
3. Reload the Sheet and choose MatchLab → **Enable 15-minute agent bridge**, then authorize.
