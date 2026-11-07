"""Grade public research snapshots only from completed, source-linked results."""
import json
from pathlib import Path
from datetime import datetime
from research import get, ESPN, LEAGUES, normalize_event, number


def outcome(row, summary):
    competition = (summary.get('header', {}).get('competitions') or [{}])[0]
    status = competition.get('status', {}).get('type', {})
    if not status.get('completed'):
        return None
    if row.get('market') == '1h':
        league = row.get('league')
        if league not in LEAGUES or LEAGUES[league][0] != 'soccer':
            return None
        game = normalize_event({'id': row.get('game_id') or row.get('id'),
                                'status': competition.get('status', {}),
                                'competitions': [competition]}, league)
        actual = (game.get('halftime') or {}).get('result')
        return ({'grade': 'Win' if actual == row['selection'] else 'Loss', 'actual': actual}
                if actual else None)
    if row.get('market') in ('nplus', 'n+'):
        label = {'points': 'PTS', 'rebounds': 'REB', 'assists': 'AST', 'threes': '3PT'}.get(row.get('stat'))
        for team in summary.get('boxscore', {}).get('players', []):
            for group in team.get('statistics', []):
                names = group.get('labels') or group.get('names') or []
                for player in group.get('athletes', []):
                    if str(player.get('athlete', {}).get('id')) != str(row.get('player_id')):
                        continue
                    if player.get('didNotPlay'):
                        return {'grade': 'DNP', 'actual': None}
                    values = dict(zip(names, player.get('stats', [])))
                    value = values.get(label)
                    if label == '3PT' and isinstance(value, str):
                        value = value.split('-')[0]
                    actual = number(value)
                    if actual is None:
                        return None
                    hit = int(actual >= row['threshold'])
                    return {'grade': 'Win' if hit else 'Loss', 'actual': hit, 'actual_value': actual}
        return None
    if row.get('market') == 'ft':
        teams = {x.get('homeAway'): x for x in competition.get('competitors', [])}
        home, away = number(teams.get('home', {}).get('score')), number(teams.get('away', {}).get('score'))
        if home is None or away is None or home == away:
            return None
        actual = 'home' if home > away else 'away'
        return {'grade': 'Win' if actual == row['selection'] else 'Loss', 'actual': actual,
                'actual_score': {'home': home, 'away': away}}
    if row.get('market') == 'total':
        # Full-game total including overtime/shootout as reported in the final score.
        teams = {x.get('homeAway'): x for x in competition.get('competitors', [])}
        home, away = number(teams.get('home', {}).get('score')), number(teams.get('away', {}).get('score'))
        line = row.get('line')
        if home is None or away is None or not isinstance(line, (int, float)) or row.get('selection') not in ('over', 'under'):
            return None
        total = home + away
        grade = 'Push' if total == line else 'Win' if (total > line) == (row['selection'] == 'over') else 'Loss'
        return {'grade': grade, 'actual': total, 'actual_score': {'home': home, 'away': away}}
    return None


def grade_files(data, now):
    cache = {}
    for name, field in [('prediction_log.json', 'predictions'), ('picks.json', 'picks')]:
        path = Path(data) / name
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        errors = []
        for row in payload.get(field, []):
            if row.get('grade') not in (None, 'Pending') or row.get('market') not in ('nplus', 'ft', '1h', 'total'):
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
                    cache[url] = json.loads(get(url))
                grade = outcome(row, cache[url])
                if grade:
                    row.update(grade, grade_source=url, graded_utc=now.isoformat())
            except Exception as exc:
                errors.append({'game_id': game_id, 'error': str(exc)[:120]})
        if field == 'predictions':
            from models import metrics
            soccer = [r for r in payload[field] if r['league'] != 'nba' and r.get('actual') is not None]
            nba = [r for r in payload[field] if r['league'] == 'nba' and r.get('actual') is not None]
            payload['forward_metrics'] = {
                'soccer': metrics([(list(r['probabilities'].values()), ['home','draw','away'].index(r['actual'])) for r in soccer]),
                'nba': metrics([([1-r['probability'], r['probability']], r['actual']) for r in nba])}
        payload['updated_utc'] = now.isoformat()
        payload['grading_errors'] = errors
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False))
        temp.replace(path)
