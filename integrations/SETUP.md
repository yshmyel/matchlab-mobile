# Secure tracker integration

The existing tracker now has MatchLab Integration, MatchLab Research and MatchLab Performance tabs. They were seeded through the authenticated Google Sheets connection. Original tabs, formulas, balances and history were not edited.

## One-time activation

1. In the tracker choose Extensions → Apps Script. Keep the project bound to this spreadsheet.
2. Add MatchLab.gs from this folder. Set appsscript.json to the supplied manifest (enable manifest display in Project Settings).
3. Set MatchLab Integration!B2 to the verified HTTPS app URL, including the trailing slash.
4. Run matchLabInstall. Google requests permission for this spreadsheet, external public feed reads and installing the time trigger. Review and authorize under your own account.
5. Verify the integration status cell and trigger list. Check the MatchLab Research and Performance tabs after a successful run.

The trigger pulls every 30 minutes, subject to Google's scheduling and quotas. It is not deployed as a public web app. No service-account keys, tokens, private exports, or public tracker sharing are needed. The source host is restricted to the expected MatchLab GitHub Pages URL. The script writes only its own named MatchLab tabs and validates their headers before updates. The public app never receives private sheet data. Device-local manual selections are separate from model-generated snapshots.

Disable through MatchLab → Disable updates. This affects only this script's MatchLab refresh trigger. Real wagers, balances and original tracker grades remain outside this integration.
