#!/usr/bin/env python3
"""Deterministic, read-only MatchLab health audit. Standard library only.

Produces evidence that the AI reviewers (Claude, Gemini) and the Sheet bridge
read; it never edits data. Usage:
    python scripts/agent_audit.py [--site URL] [--json out.json] [--markdown out.md]
Exit code: 0 OK/WARN, 1 FAIL (so a scheduled run shows red on real faults).
"""
import argparse, json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from research import pacific_date  # noqa: E402

SITE = 'https://yshmyel.github.io/matchlab-mobile/'
REPO = 'yshmyel/matchlab-mobile'
FEED_WARN, FEED_FAIL = timedelta(minutes=75), timedelta(hours=3)
GRADE_OVERDUE = timedelta(hours=6)   # game start + 6h with no grade = reconcile


def fetch(url, token=None):
    headers = {'User-Agent': 'MatchLabAudit/1.0', 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
        return json.loads(r.read().decode('utf-8-sig'))


def parse(ts):
    try:
        return datetime.fromisoformat(str(ts).replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError:
        return None


def check_feed(site, now, get=fetch):
    out = []
    try:
        feed = get(site.rstrip('/') + '/data/latest.json?audit=' + str(int(now.timestamp())))
    except Exception as exc:
        return [('FAIL', 'feed', f'Published feed unreachable: {str(exc)[:120]}')]
    gen = parse(feed.get('generated_utc'))
    if not gen:
        out.append(('FAIL', 'feed', 'Published feed has no valid generated_utc'))
    else:
        age = now - gen
        level = 'FAIL' if age > FEED_FAIL else 'WARN' if age > FEED_WARN else 'OK'
        out.append((level, 'feed', f'Feed generated {gen:%Y-%m-%d %H:%M} UTC ({int(age.total_seconds() // 60)} min old)'))
    today = pacific_date(now.isoformat())
    if feed.get('date') != today:
        out.append(('FAIL', 'feed', f"Feed slate date {feed.get('date')} is not Pacific today {today}"))
    if feed.get('errors'):
        out.append(('WARN', 'feed', 'Feed source errors: ' + ', '.join(sorted(feed['errors']))[:200]))
    counts = feed.get('counts') or {}
    out.append(('OK', 'feed', f"{len(feed.get('games') or [])} games; counts {json.dumps(counts, sort_keys=True)[:200]}"))
    return out


def check_grades(data_dir, now):
    out = []
    for name, field in [('picks.json', 'picks'), ('prediction_log.json', 'predictions')]:
        path = Path(data_dir) / name
        if not path.exists():
            out.append(('FAIL', 'grading', f'{name} missing'))
            continue
        payload = json.loads(path.read_text(encoding='utf-8'))
        rows = payload.get(field, [])
        overdue, unsourced = [], []
        for r in rows:
            if r.get('market') == 'pass' or r.get('selection') == 'none':
                continue
            start = parse(r.get('game_date') or r.get('kickoff') or '')
            graded = r.get('grade') not in (None, 'Pending')
            if graded and not r.get('grade_source'):
                unsourced.append(r.get('id') or r.get('key'))
            if not graded and start and now - start > GRADE_OVERDUE:
                overdue.append(r.get('id') or r.get('key') or r.get('game_id'))
        if overdue:
            out.append(('WARN', 'grading', f'{name}: {len(overdue)} past-due ungraded: ' + ', '.join(map(str, overdue[:8]))))
        if unsourced:
            out.append(('FAIL', 'grading', f'{name}: {len(unsourced)} grades lack grade_source: ' + ', '.join(map(str, unsourced[:8]))))
        if payload.get('grading_errors'):
            out.append(('WARN', 'grading', f"{name}: {len(payload['grading_errors'])} grading errors last run"))
        if not overdue and not unsourced:
            out.append(('OK', 'grading', f'{name}: {len(rows)} rows, nothing past due, all grades sourced'))
    return out


def check_workflows(now, token=None, get=fetch):
    try:
        runs = get(f'https://api.github.com/repos/{REPO}/actions/runs?per_page=30', token)['workflow_runs']
    except Exception as exc:
        return [('WARN', 'actions', f'Could not read workflow runs: {str(exc)[:100]}')]
    out, latest = [], {}
    for run in runs:
        latest.setdefault(run['name'], run)
    for name, run in sorted(latest.items()):
        if run.get('conclusion') in ('failure', 'timed_out', 'startup_failure'):
            out.append(('FAIL' if name.startswith('Refresh') else 'WARN', 'actions',
                        f"Latest '{name}' run {run['conclusion']}: {run['html_url']}"))
    deploys = [r for r in runs if r['name'].startswith('Refresh') and r.get('conclusion') == 'success']
    if deploys:
        gap = now - parse(deploys[0]['updated_at'])
        level = 'WARN' if gap > FEED_WARN else 'OK'
        out.append((level, 'actions', f"Last successful deploy {int(gap.total_seconds() // 60)} min ago: {deploys[0]['html_url']}"))
    else:
        out.append(('FAIL', 'actions', 'No successful deploy in the last 30 runs'))
    return out


def summarize(findings):
    worst = 'FAIL' if any(f[0] == 'FAIL' for f in findings) else 'WARN' if any(f[0] == 'WARN' for f in findings) else 'OK'
    return worst


def markdown(findings, now):
    icon = {'OK': '✅', 'WARN': '⚠️', 'FAIL': '❌'}
    lines = [f'**Overall: {summarize(findings)}** · checked {now:%Y-%m-%d %H:%M} UTC', '',
             '| | Area | Finding |', '|---|---|---|']
    lines += [f'| {icon[l]} {l} | {a} | {m.replace("|", "/")} |' for l, a, m in findings]
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--site', default=SITE)
    p.add_argument('--data', default=str(ROOT / 'data'))
    p.add_argument('--json')
    p.add_argument('--markdown')
    a = p.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    now = datetime.now(timezone.utc)
    token = os.environ.get('GITHUB_TOKEN')
    findings = check_feed(a.site, now) + check_grades(a.data, now) + check_workflows(now, token)
    md = markdown(findings, now)
    if a.json:
        Path(a.json).write_text(json.dumps({'checked_utc': now.isoformat(), 'overall': summarize(findings),
                                            'findings': [dict(level=l, area=ar, message=m) for l, ar, m in findings]},
                                           indent=2, ensure_ascii=False), encoding='utf-8')
    if a.markdown:
        Path(a.markdown).write_text(md, encoding='utf-8')
    print(md)
    return 1 if summarize(findings) == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
