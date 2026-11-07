#!/usr/bin/env python3
"""Read-only reconciliation report: the shared evidence for Claude, Gemini and ChatGPT.

Accounts for every public research record, explains why the model archive and the
editorial shortlist have different sizes, re-verifies already graded rows against
the ESPN result they cite (without changing them), and lists overdue Pending rows.

  python scripts/reconcile.py --json .agent/evidence/reconciliation.json \
      --markdown .agent/evidence/reconciliation.md [--verify] [--offline]

Never writes to data/. Conflicts are reported, never "fixed" by overwriting history.
"""
import argparse, json, sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from grading import SETTLED, outcome, value_status, row_key  # noqa: E402
from research import get, pacific_date  # noqa: E402


def load(data):
    log = json.loads((data / 'prediction_log.json').read_text())
    picks = json.loads((data / 'picks.json').read_text())
    return log.get('predictions', []), picks.get('picks', [])


def game_key(r):
    return f"{r.get('league')}:{r.get('game_id') or r.get('id')}"


def account(log, picks):
    """Why does the Sheet show N research snapshots while picks.json has M records?"""
    nba = [r for r in log if r.get('league') == 'nba']
    combos = Counter((r.get('game_id'), r.get('player_id')) for r in nba)
    log_games = {game_key(r) for r in log}
    selections = [p for p in picks if p.get('market') != 'pass']
    in_log = [p for p in selections if p.get('market') in ('nplus', '1h') and any(
        r.get('league') == p.get('league') and str(r.get('game_id') or r.get('id')) == str(p.get('game_id'))
        and (p.get('market') == '1h' or (str(r.get('player_id')) == str(p.get('player_id')) and r.get('stat') == p.get('stat')
                                         and r.get('threshold') == p.get('threshold'))) for r in log)]
    return {
        'prediction_log_records': len(log),
        'picks_records': len(picks),
        'prediction_log_by_market': dict(Counter(f"{r.get('league')}:{r.get('market')}" for r in log)),
        'picks_by_market': dict(Counter(f"{p.get('league')}:{p.get('market')}" for p in picks)),
        'nba_player_games': len(combos),
        'nba_thresholds_per_player_game': sorted(set(combos.values())),
        'editorial_selections': len(selections),
        'editorial_passes': len(picks) - len(selections),
        'editorial_selections_with_matching_model_snapshot': len(in_log),
        'editorial_markets_without_model': dict(Counter(p['market'] for p in selections if p.get('market') not in ('nplus', '1h'))),
        'games_in_model_log': len(log_games),
        'explanation': (
            'Intentional, not missing data. The Sheet tab "MatchLab Research" mirrors data/prediction_log.json: '
            'every automated model snapshot (each eligible NBA player x 4 fixed N+ thresholds, plus soccer 1H '
            'forecasts). data/picks.json is the separate editorial shortlist (selections and passes chosen by '
            'researchers, including NHL markets the model does not produce). The real gap: the Sheet sync never '
            'imported picks.json, so editorial picks reached the Sheet only through manual day tabs.'),
    }


def integrity(rows, label):
    keys = Counter(row_key(r) for r in rows)
    return {
        'file': label,
        'records': len(rows),
        'duplicate_keys': [k for k, n in keys.items() if n > 1],
        'settled_without_source': [row_key(r) for r in rows if r.get('grade') in SETTLED and not r.get('grade_source')],
        'pass_with_grade': [row_key(r) for r in rows if r.get('market') == 'pass' and r.get('grade') in ('Win', 'Loss', 'Push')],
        'grades': dict(Counter(r.get('grade') or 'Pending' for r in rows)),
        'value_status': dict(Counter(value_status(r) for r in rows)),
    }


def overdue(rows, now):
    """Pending rows whose event should have a result by now (3h after start)."""
    out = []
    for r in rows:
        when = r.get('game_date') or r.get('kickoff')
        if r.get('market') == 'pass' or (r.get('grade') or 'Pending') != 'Pending' or not when:
            continue
        start = datetime.fromisoformat(when.replace('Z', '+00:00'))
        if now - start > timedelta(hours=3):
            out.append({'key': row_key(r), 'league': r.get('league'), 'market': r.get('market'),
                        'start_utc': when, 'pacific_date': pacific_date(when)})
    return out


def verify(rows, label, fetch):
    """Recompute each settled grade from its cited source; report disagreements only."""
    checked, conflicts, unverifiable, cache = 0, [], [], {}
    for r in rows:
        src = r.get('grade_source') or ''
        if r.get('grade') not in SETTLED or '/summary?event=' not in src:
            continue
        try:
            if src not in cache:
                cache[src] = fetch(src)
            again = outcome(r, cache[src])
        except Exception as exc:
            unverifiable.append({'key': row_key(r), 'error': str(exc)[:120]}); continue
        if not again:
            unverifiable.append({'key': row_key(r), 'error': 'source no longer reports a result'}); continue
        checked += 1
        if again['grade'] != r['grade']:
            conflicts.append({'key': row_key(r), 'recorded': r['grade'], 'source_now': again['grade'], 'source': src})
    gamelog = sum(1 for r in rows if r.get('grade') in SETTLED and '/gamelog' in (r.get('grade_source') or ''))
    return {'file': label, 'rechecked': checked, 'conflicts': conflicts, 'unverifiable': unverifiable,
            'settled_from_player_gamelog_not_rechecked': gamelog}


def markdown(report):
    a, lines = report['accounting'], []
    lines += [f"# MatchLab reconciliation · {report['generated_utc']}", '',
              f"**Model archive** `prediction_log.json`: {a['prediction_log_records']} · "
              f"**Editorial shortlist** `picks.json`: {a['picks_records']} "
              f"({a['editorial_selections']} selections, {a['editorial_passes']} passes)", '', a['explanation'], '',
              f"- NBA snapshots: {a['nba_player_games']} player-games x {a['nba_thresholds_per_player_game']} thresholds",
              f"- Editorial selections that also have a model snapshot: {a['editorial_selections_with_matching_model_snapshot']}",
              f"- Editorial markets the model never produces: {a['editorial_markets_without_model']}", '',
              '## Integrity', '', '| File | Records | Duplicates | Settled w/o source | PASS graded | Grades | Value status |',
              '|---|---|---|---|---|---|---|']
    for i in report['integrity']:
        lines.append(f"| {i['file']} | {i['records']} | {len(i['duplicate_keys'])} | {len(i['settled_without_source'])} | "
                     f"{len(i['pass_with_grade'])} | {i['grades']} | {i['value_status']} |")
    lines += ['', f"## Overdue Pending ({len(report['overdue'])})", '']
    lines += [f"- `{o['key']}` {o['league']} {o['market']} start {o['start_utc']}" for o in report['overdue'][:60]] or ['- none']
    for v in report.get('verification', []):
        lines += ['', f"## Re-verification · {v['file']}", '',
                  f"Rechecked {v['rechecked']} against cited ESPN summaries; conflicts {len(v['conflicts'])}; "
                  f"unverifiable {len(v['unverifiable'])}; gamelog-sourced (not rechecked here) {v['settled_from_player_gamelog_not_rechecked']}."]
        lines += [f"- CONFLICT `{c['key']}` recorded {c['recorded']}, source now {c['source_now']} ({c['source']})" for c in v['conflicts']]
    return '\n'.join(lines) + '\n'


def build(data=ROOT / 'data', now=None, verify_grades=False, fetch=None):
    now = now or datetime.now(timezone.utc)
    log, picks = load(Path(data))
    report = {'schema_version': 1, 'generated_utc': now.isoformat(), 'accounting': account(log, picks),
              'integrity': [integrity(log, 'prediction_log.json'), integrity(picks, 'picks.json')],
              'overdue': overdue(log + picks, now)}
    if verify_grades:
        fetch = fetch or (lambda url: json.loads(get(url)))
        report['verification'] = [verify(log, 'prediction_log.json', fetch), verify(picks, 'picks.json', fetch)]
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--json'); p.add_argument('--markdown'); p.add_argument('--verify', action='store_true')
    a = p.parse_args()
    rep = build(verify_grades=a.verify)
    for path, text in [(a.json, json.dumps(rep, indent=2)), (a.markdown, markdown(rep))]:
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True); Path(path).write_text(text)
    print(markdown(rep))
    bad = any(i['duplicate_keys'] or i['pass_with_grade'] for i in rep['integrity']) or any(v['conflicts'] for v in rep.get('verification', []))
    sys.exit(1 if bad else 0)
