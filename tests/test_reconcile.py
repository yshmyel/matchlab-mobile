import json, sys, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grading import outcome, halftime_score, value_status, check_invariants, grade_files  # noqa: E402

NOW = datetime(2026, 11, 7, 19, 0, tzinfo=timezone.utc)


def soccer(name, period, ht, full=None, completed=False):
    """ESPN-shaped summary. ht/full are (home, away)."""
    lines = lambda i: [{'value': ht[i]}] + ([{'value': full[i] - ht[i]}] if full else [])
    score = full or ht
    return {'header': {'competitions': [{'status': {'period': period, 'type': {'name': name, 'completed': completed}},
            'competitors': [{'homeAway': 'home', 'score': str(score[0]), 'linescores': lines(0)},
                            {'homeAway': 'away', 'score': str(score[1]), 'linescores': lines(1)}]}]}}


def final(home, away):
    return {'header': {'competitions': [{'status': {'type': {'name': 'STATUS_FINAL', 'completed': True}},
            'competitors': [{'homeAway': 'home', 'score': str(home)}, {'homeAway': 'away', 'score': str(away)}]}]}}


class HalftimeGrading(unittest.TestCase):
    row = {'market': '1h', 'league': 'serie_a', 'selection': 'draw'}

    def test_grades_at_halftime_without_waiting_for_full_time(self):
        g = outcome(self.row, soccer('STATUS_HALFTIME', 1, (0, 0)))
        self.assertEqual((g['grade'], g['actual'], g['result_basis']), ('Win', 'draw', 'halftime_score'))
        self.assertEqual(g['actual_score'], {'home': 0, 'away': 0})

    def test_second_half_uses_period_one_score_not_running_score(self):
        g = outcome(self.row, soccer('STATUS_SECOND_HALF', 2, (0, 0), (0, 1)))
        self.assertEqual(g['grade'], 'Win')

    def test_live_first_half_is_not_a_result(self):
        self.assertIsNone(outcome(self.row, soccer('STATUS_FIRST_HALF', 1, (1, 0))))
        self.assertIsNone(halftime_score(soccer('STATUS_FIRST_HALF', 1, (0, 0))))

    def test_postponed_or_inconsistent_source_is_never_graded(self):
        self.assertIsNone(outcome(self.row, soccer('STATUS_POSTPONED', 2, (0, 0))))
        bad = soccer('STATUS_FINAL', 2, (2, 0), (2, 1), completed=True)
        bad['header']['competitions'][0]['competitors'][0]['score'] = '1'  # HT goals exceed FT
        self.assertIsNone(halftime_score(bad))

    def test_full_game_markets_still_wait_for_completion(self):
        self.assertIsNone(outcome({'market': 'ft', 'selection': 'home'}, soccer('STATUS_SECOND_HALF', 2, (1, 0), (2, 0))))
        self.assertEqual(outcome({'market': 'ft', 'selection': 'home'}, final(4, 1))['grade'], 'Win')
        self.assertEqual(outcome({'market': 'total', 'selection': 'under', 'line': 6}, final(4, 2))['grade'], 'Push')


class SourceShapes(unittest.TestCase):
    def test_summary_linescores_with_only_display_value(self):
        # Real ESPN summary shape (Venezia v Udinese 401874815): no numeric 'value'.
        s = soccer('STATUS_FULL_TIME', 2, (0, 0), (2, 1), completed=True)
        for side in s['header']['competitions'][0]['competitors']:
            side['linescores'] = [{'displayValue': str(x['value'])} for x in side['linescores']]
        self.assertEqual(halftime_score(s), {'home': 0, 'away': 0})

    def test_player_absent_from_complete_boxscore_is_dnp_not_loss(self):
        team = lambda ids: {'statistics': [{'labels': ['PTS'], 'athletes': [{'athlete': {'id': i}, 'stats': ['10']} for i in ids]}]}
        box = final(110, 100); box['boxscore'] = {'players': [team('12345'), team('67890')]}
        row = {'market': 'nplus', 'stat': 'points', 'threshold': 20, 'player_id': '999'}
        self.assertEqual(outcome(row, box)['grade'], 'DNP')
        box['boxscore'] = {'players': [team('12345')]}  # incomplete box score: stay pending
        self.assertIsNone(outcome(row, box))


class ValueLabels(unittest.TestCase):
    def test_unpriced_or_reference_only_research_is_research_only(self):
        self.assertEqual(value_status({'market': '1h', 'selection': 'draw', 'odds': None}), 'RESEARCH ONLY')
        self.assertEqual(value_status({'market': 'ft', 'selection': 'home',
                                       'reference_odds': [{'bookmaker': 'ESPN BET'}]}), 'RESEARCH ONLY')

    def test_verified_matching_price_enables_value_assessment(self):
        odds = {'bookmaker': 'FanDuel', 'american': -150, 'observed_utc': '2026-11-07T17:00:00Z',
                'source_url': 'https://example.test/q', 'market': 'ft', 'selection': 'home', 'line': None}
        self.assertEqual(value_status({'market': 'ft', 'selection': 'home', 'verified_odds': odds}), 'VALUE ASSESSED')
        self.assertEqual(value_status({'market': 'ft', 'selection': 'away', 'verified_odds': odds}), 'RESEARCH ONLY')


class Invariants(unittest.TestCase):
    base = {'id': 'a', 'market': 'ft', 'selection': 'home', 'grade': 'Win', 'actual': 'home'}

    def test_rejects_pass_conversion_regrade_removal_and_duplicates(self):
        for after in ([dict(self.base, market='pass', selection='none')], [dict(self.base, grade='Pending')],
                      [], [self.base, dict(self.base)], [dict(self.base, actual='away')]):
            with self.assertRaises(ValueError):
                check_invariants([self.base], after)

    def test_allows_new_grades_and_additive_fields(self):
        pending = dict(self.base, grade='Pending'); pending.pop('actual')
        check_invariants([pending], [dict(self.base, value_status='RESEARCH ONLY')])


class GradeFilesPipeline(unittest.TestCase):
    def test_end_to_end_grading_is_idempotent_and_keeps_pass_ungraded(self):
        picks = [{'id': 'p-1h', 'league': 'serie_a', 'game_id': '1', 'market': '1h', 'selection': 'draw', 'grade': 'Pending',
                  'game_date': '2026-11-07T17:00:00Z'},
                 {'id': 'p-pass', 'league': 'nhl', 'game_id': '2', 'market': 'pass', 'selection': 'none',
                  'grade': 'Not applicable', 'status': 'PASS', 'game_date': '2026-11-07T00:00:00Z'},
                 {'id': 'p-old', 'league': 'nhl', 'game_id': '2', 'market': 'ft', 'selection': 'away', 'grade': 'Loss',
                  'actual': 'home', 'grade_source': 'orig', 'game_date': '2026-11-07T00:00:00Z'},
                 {'id': 'p-future', 'league': 'nhl', 'game_id': '3', 'market': 'ft', 'selection': 'home', 'grade': 'Pending',
                  'game_date': '2026-11-08T03:00:00Z'}]
        sources = {'1': soccer('STATUS_SECOND_HALF', 2, (0, 0), (0, 1)), '2': final(5, 2)}
        calls = []
        fetch = lambda url: calls.append(url) or sources[url.rsplit('=', 1)[1]]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'picks.json'
            path.write_text(json.dumps({'schema_version': 1, 'picks': picks}))
            first = grade_files(d, NOW, fetch)
            rows = {r['id']: r for r in json.loads(path.read_text())['picks']}
            self.assertEqual(rows['p-1h']['grade'], 'Win')
            self.assertIn('summary?event=1', rows['p-1h']['grade_source'])
            self.assertEqual(rows['p-pass']['grade'], 'Not applicable')
            self.assertEqual(rows['p-pass']['market'], 'pass')
            self.assertEqual(rows['p-pass']['official_result'], {'final_score': {'home': 5, 'away': 2}})
            self.assertEqual((rows['p-old']['grade'], rows['p-old']['grade_source']), ('Loss', 'orig'))
            self.assertEqual(rows['p-future']['grade'], 'Pending')
            self.assertTrue(all(r['value_status'] == 'RESEARCH ONLY' for r in rows.values()))
            self.assertEqual(len(first['graded']), 1)
            snapshot = path.read_text()
            second = grade_files(d, NOW, fetch)
            self.assertEqual(second['graded'], [])
            self.assertEqual(len(json.loads(path.read_text())['picks']), 4)
            self.assertEqual(json.loads(path.read_text())['picks'], json.loads(snapshot)['picks'])

    def test_missing_result_stays_pending(self):
        def broken(url):
            raise OSError('timeout')
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'picks.json'
            path.write_text(json.dumps({'picks': [{'id': 'x', 'league': 'nba', 'game_id': '9', 'market': 'nplus', 'stat': 'points',
                                                   'threshold': 20, 'selection': 'hit', 'grade': 'Pending', 'game_date': '2026-11-07T00:00:00Z'}]}))
            out = grade_files(d, NOW, broken)
            self.assertEqual(json.loads(path.read_text())['picks'][0]['grade'], 'Pending')
            self.assertEqual(len(out['errors']), 1)


if __name__ == '__main__':
    unittest.main()
