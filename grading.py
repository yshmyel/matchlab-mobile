"""Grade public research snapshots only from source-linked official results.

Settlement rules (see AGENTS.md):
- Soccer 1H markets settle at halftime: the ESPN period-1 score once the match
  is at halftime, in the second half, or final. Full-game completion is not
  required and a running first-half score is never used.
- NBA N+ milestones and NHL/NBA full-game moneyline/totals settle only on a
  completed game. A total exactly on the line is a Push; a reported DNP is DNP.
- A PASS published pregame has no selection, so it is never graded Win/Loss.
  Its official result is recorded for audit only.
- An existing selection is never converted to PASS, regraded, removed or
  rewritten. Missing results stay Pending. check_invariants() enforces this on
  every write.
"""
import json
from pathlib import Path
from datetime import datetime
from research import get, ESPN, LEAGUES, number

SETTLED = {'Win', 'Loss', 'Push', 'DNP'}
GRADABLE = {'nplus', 'n+', 'ft', '1h', 'total'}
IMMUTABLE = ('market', 'selection', 'threshold', 'line', 'stat', 'player_id', 'game_id',
             'generated_utc', 'published_utc', 'label')
STAT_LABEL = {'points': 'PTS', 'rebounds': 'REB', 'assists': 'AST', 'threes': '3PT'}


def _competition(summary):
    return (summary.get('header', {}).get('competitions') or [{}])[0]


def _sides(competition):
    return {x.get('homeAway'): x for x in competition.get('competitors', [])}


def final_score(summary):
    """Reported final score {'home','away'} of a completed game, else None."""
    c = _competition(summary)
    if not c.get('status', {}).get('type', {}).get('completed'):
        return None
    t = _sides(c)
    home, away = number(t.get('home', {}).get('score')), number(t.get('away', {}).get('score'))
    return None if home is None or away is None else {'home': home, 'away': away}


def halftime_score(summary):
    """Verified first-half score of a soccer match, else None.

    Accepted only once the first half has ended (halftime, period 2+, or final);
    a live first-half score is not a result.
    """
    c = _competition(summary)
    status = c.get('status', {})
    kind = status.get('type', {})
    ended = (kind.get('completed') or kind.get('name') == 'STATUS_HALFTIME'
             or (number(status.get('period')) or 0) >= 2)
    if not ended or kind.get('name') in ('STATUS_POSTPONED', 'STATUS_CANCELED', 'STATUS_ABANDONED'):
        return None
    t = _sides(c)
    try:
        home = number(t['home']['linescores'][0].get('value', t['home']['linescores'][0].get('displayValue')))
        away = number(t['away']['linescores'][0].get('value', t['away']['linescores'][0].get('displayValue')))
    except (KeyError, IndexError, TypeError, AttributeError):
        return None
    if home is None or away is None or home < 0 or away < 0:
        return None
    full = final_score(summary)
    if full and (home > full['home'] or away > full['away']):
        return None  # inconsistent source data: never grade from it
    return {'home': home, 'away': away}


def _side(score):
    return 'home' if score['home'] > score['away'] else 'away' if score['away'] > score['home'] else 'draw'


def outcome(row, summary):
    """Grade fields for one pending row, or None when no verified result exists."""
    market = row.get('market')
    if market == '1h':
        league = row.get('league')
        if league not in LEAGUES or LEAGUES[league][0] != 'soccer':
            return None
        ht = halftime_score(summary)
        if not ht:
            return None
        actual = _side(ht)
        return {'grade': 'Win' if actual == row['selection'] else 'Loss', 'actual': actual,
                'actual_score': ht, 'result_basis': 'halftime_score'}
    if not _competition(summary).get('status', {}).get('type', {}).get('completed'):
        return None
    if market in ('nplus', 'n+'):
        label = STAT_LABEL.get(row.get('stat'))
        for team in summary.get('boxscore', {}).get('players', []):
            for group in team.get('statistics', []):
                names = group.get('labels') or group.get('names') or []
                for player in group.get('athletes', []):
                    if str(player.get('athlete', {}).get('id')) != str(row.get('player_id')):
                        continue
                    if player.get('didNotPlay'):
                        return {'grade': 'DNP', 'actual': None, 'result_basis': 'player_boxscore'}
                    value = dict(zip(names, player.get('stats', []))).get(label)
                    if label == '3PT' and isinstance(value, str):
                        value = value.split('-')[0]
                    actual = number(value)
                    if actual is None:
                        return None
                    hit = int(actual >= row['threshold'])
                    return {'grade': 'Win' if hit else 'Loss', 'actual': hit, 'actual_value': actual,
                            'result_basis': 'player_boxscore'}
        # Inactive players are omitted from ESPN's final box score. Only when the
        # box score is complete for both teams does absence mean did-not-play.
        # DNP is never a loss and is excluded from hit-rate metrics.
        teams = summary.get('boxscore', {}).get('players', [])
        if len(teams) == 2 and all(sum(len(g.get('athletes', [])) for g in t.get('statistics', [])) >= 5 for t in teams):
            return {'grade': 'DNP', 'actual': None, 'result_basis': 'absent_from_final_boxscore'}
        return None
    score = final_score(summary)
    if not score:
        return None
    if market == 'ft':
        if score['home'] == score['away']:
            return None
        actual = _side(score)
        return {'grade': 'Win' if actual == row['selection'] else 'Loss', 'actual': actual,
                'actual_score': score, 'result_basis': 'final_score'}
    if market == 'total':
        # Full-game total including overtime/shootout as reported in the final score.
        line = row.get('line')
        if not isinstance(line, (int, float)) or row.get('selection') not in ('over', 'under'):
            return None
        total = score['home'] + score['away']
        grade = 'Push' if total == line else 'Win' if (total > line) == (row['selection'] == 'over') else 'Loss'
        return {'grade': grade, 'actual': total, 'actual_score': score, 'result_basis': 'final_score'}
    return None


def official_result(row, summary):
    """Audit-only official result for a published PASS. Never a grade."""
    score = final_score(summary)
    if not score:
        return None
    result = {'final_score': score}
    if LEAGUES.get(row.get('league'), ('',))[0] == 'soccer':
        ht = halftime_score(summary)
        if ht:
            result['halftime_score'] = ht
    return result


def value_status(row):
    """RESEARCH ONLY until a verified sportsbook price for this exact market exists.

    A verified price needs bookmaker, American odds, quote/observation time and a
    source URL, matching the row's market, selection and line. ESPN reference
    snapshots and unpriced research never qualify.
    """
    odds = row.get('verified_odds')
    if (isinstance(odds, dict) and all(odds.get(k) not in (None, '') for k in ('bookmaker', 'american', 'observed_utc', 'source_url'))
            and odds.get('market') == row.get('market') and odds.get('selection') == row.get('selection')
            and odds.get('line') == row.get('line') and number(odds.get('american')) is not None and abs(number(odds['american'])) >= 100):
        return 'VALUE ASSESSED'
    return 'RESEARCH ONLY'


def row_key(row):
    return str(row.get('key') or row.get('id'))


def check_invariants(before, after):
    """Raise ValueError if a write would lose history or rewrite a selection/grade."""
    seen = set()
    for r in after:
        k = row_key(r)
        if k in seen:
            raise ValueError(f'duplicate record {k}')
        seen.add(k)
    now = {row_key(r): r for r in after}
    for old in before:
        k = row_key(old)
        new = now.get(k)
        if new is None:
            raise ValueError(f'record {k} would be removed')
        if old.get('market') != 'pass' and new.get('market') == 'pass':
            raise ValueError(f'record {k} would be converted to PASS')
        for field in IMMUTABLE:
            if old.get(field) != new.get(field):
                raise ValueError(f'record {k} field {field} would change')
        if old.get('grade') in SETTLED | {'Not applicable'} and new.get('grade') != old.get('grade'):
            raise ValueError(f'record {k} grade {old.get("grade")} would change to {new.get("grade")}')
        for field in ('actual', 'actual_value', 'actual_score', 'grade_source', 'graded_utc', 'cashout', 'stake'):
            if old.get('grade') in SETTLED and field in old and old[field] != new.get(field):
                raise ValueError(f'record {k} settled field {field} would change')


def grade_files(data, now, fetch=None):
    """Grade pending rows in place. Returns {'graded': [...], 'errors': [...]}."""
    fetch = fetch or (lambda url: json.loads(get(url)))
    cache, summary = {}, {'graded': [], 'pass_results': [], 'errors': []}
    for name, field in [('prediction_log.json', 'predictions'), ('picks.json', 'picks')]:
        path = Path(data) / name
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        rows = payload.get(field, [])
        before = json.loads(json.dumps(rows))
        errors = []
        for row in rows:
            row['value_status'] = value_status(row)
            row.setdefault('placement', 'UNPLACED RESEARCH')
            is_pass = row.get('market') == 'pass'
            if is_pass and row.get('official_result'):
                continue
            if not is_pass and (row.get('grade') not in (None, 'Pending') or row.get('market') not in GRADABLE):
                continue
            date = row.get('game_date') or row.get('kickoff')
            if not date or datetime.fromisoformat(date.replace('Z', '+00:00')) > now:
                continue
            league = row.get('league')
            if league not in LEAGUES:
                continue
            game_id = str(row.get('game_id') or row.get('id'))
            sport, slug = LEAGUES[league]
            url = f'{ESPN}/{sport}/{slug}/summary?event={game_id}'
            try:
                if url not in cache:
                    cache[url] = fetch(url)
                if is_pass:
                    result = official_result(row, cache[url])
                    if result:
                        row.update(official_result=result, official_result_source=url,
                                   official_result_utc=now.isoformat())
                        summary['pass_results'].append(row_key(row))
                    continue
                grade = outcome(row, cache[url])
                if grade:
                    row.update(grade, grade_source=url, graded_utc=now.isoformat())
                    summary['graded'].append({'file': name, 'key': row_key(row), 'grade': grade['grade'],
                                              'basis': grade.get('result_basis'), 'source': url})
            except Exception as exc:
                errors.append({'game_id': game_id, 'error': str(exc)[:120]})
        check_invariants(before, rows)
        if field == 'predictions':
            from models import metrics
            soccer = [r for r in rows if r['league'] != 'nba' and r.get('actual') in ('home', 'draw', 'away') and r.get('probabilities')]
            nba = [r for r in rows if r['league'] == 'nba' and r.get('actual') in (0, 1)]
            payload['forward_metrics'] = {
                'soccer': metrics([(list(r['probabilities'].values()), ['home', 'draw', 'away'].index(r['actual'])) for r in soccer]),
                'nba': metrics([([1 - r['probability'], r['probability']], r['actual']) for r in nba])}
        payload['updated_utc'] = now.isoformat()
        payload['grading_errors'] = errors
        summary['errors'] += errors
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False))
        temp.replace(path)
    return summary
