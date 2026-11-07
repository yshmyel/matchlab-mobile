import json, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import research
from research import pacific_date


class PacificSlateTests(unittest.TestCase):
    def test_standard_time_late_start_stays_on_pacific_day(self):
        # Nov 8 03:30 UTC is Nov 7 7:30 PM PST.
        self.assertEqual(pacific_date('2026-11-08T03:30Z'), '20261107')

    def test_daylight_time_offset(self):
        # Jul 1 06:30 UTC is Jun 30 11:30 PM PDT.
        self.assertEqual(pacific_date('2026-07-01T06:30Z'), '20260630')

    def test_unparseable_date_is_unknown(self):
        self.assertIsNone(pacific_date('not-a-date'))

    def test_fallback_rule_matches_transition_dates(self):
        with patch.dict('sys.modules', {'zoneinfo': None}):
            self.assertEqual(pacific_date('2026-11-01T08:30Z'), '20261101')  # 1:30 AM PDT
            self.assertEqual(pacific_date('2026-11-02T07:30Z'), '20261101')  # 11:30 PM PST
            self.assertEqual(pacific_date('2026-03-08T09:30Z'), '20260308')  # 1:30 AM PST

    def test_scoreboard_includes_late_pt_game_listed_on_next_espn_day(self):
        g = lambda i, t: {'id': i, 'date_utc': t}
        days = {'20261107': [g('a', '2026-11-07T18:00Z'), g('early', '2026-11-07T05:00Z')],
                '20261108': [g('late', '2026-11-08T06:00Z'), g('next', '2026-11-08T20:00Z'), g('a', '2026-11-07T18:00Z')]}
        with patch.object(research, '_espn_day', side_effect=lambda lg, d: days[d]):
            ids = sorted(x['id'] for x in research.scoreboard('nba', '20261107'))
        # 'early' is Nov 6 PT; 'late' is Nov 7 10 PM PT; 'next' is Nov 8 PT; 'a' deduped.
        self.assertEqual(ids, ['a', 'late'])

    def test_next_day_failure_keeps_primary_day(self):
        def fake(lg, d):
            if d == '20261108': raise OSError('offline')
            return [{'id': 'a', 'date_utc': '2026-11-07T18:00Z'}]
        with patch.object(research, '_espn_day', side_effect=fake):
            self.assertEqual([x['id'] for x in research.scoreboard('nba', '20261107')], ['a'])

    def test_primary_day_failure_raises(self):
        with patch.object(research, '_espn_day', side_effect=OSError('offline')):
            with self.assertRaises(OSError): research.scoreboard('nba', '20261107')


class GradeProvenanceTests(unittest.TestCase):
    def test_gamelog_grade_records_source(self):
        import pipeline
        with tempfile.TemporaryDirectory() as d:
            row = {'key': 'k', 'league': 'nba', 'player_id': '9', 'game_id': 'g1', 'stat': 'points',
                   'threshold': 20, 'probability': .6, 'grade': 'Pending'}
            Path(d, 'prediction_log.json').write_text(json.dumps({'schema_version': 1, 'predictions': [row]}))
            actuals = {'9': [{'id': 'g1', 'points': 24, 'source': 'https://example.test/gamelog'}]}
            with patch.object(pipeline, 'DATA', Path(d)):
                pipeline.archive_predictions({'predictions': [], 'nba_props': [], 'games': []},
                                             datetime(2026, 11, 7, tzinfo=timezone.utc), {}, actuals)
            out = json.loads(Path(d, 'prediction_log.json').read_text())['predictions'][0]
        self.assertEqual((out['grade'], out['grade_source']), ('Win', 'https://example.test/gamelog'))


if __name__ == '__main__': unittest.main()
