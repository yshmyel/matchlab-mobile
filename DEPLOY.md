# Publish MatchLab

1. Create `matchlab-mobile` in the desired GitHub account. Public repositories support free Pages hosting; private repository Pages depends on plan.
2. Push this folder's contents to the repository root on `main`, including `.github/workflows/pages.yml`. Do not upload device research logs or credentials.
3. Settings → Pages → Build and deployment → Source → GitHub Actions.
4. Run Actions → Refresh and deploy MatchLab → Run workflow if the first push ran before Pages was enabled.
5. Confirm the deploy and published-site verification steps succeed. The workflow exposes the actual Pages URL.
6. Open that URL in Safari → Share → Add to Home Screen.

The workflow rebuilds both current and prior Pacific dates and deploys the resulting files directly. It does not rely on a bot commit triggering another workflow. An all-provider outage fails the run and retains the existing live deployment. Partial league failures deploy with explicit coverage warnings. No API key or personal access token is needed for data refreshes.

Scheduled runs are best effort, not live streaming. Re-enable workflows if GitHub disables them due to inactivity. The app displays feed timestamps and warnings.
