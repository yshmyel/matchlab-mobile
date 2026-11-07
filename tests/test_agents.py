import json, sys, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import agent_audit  # noqa: E402
import grade_now  # noqa: E402

NOW = datetime(2026, 11, 7, 20, 0, tzinfo=timezone.utc)  # 12:00 PST, Pacific date 20261107


class AuditTests(unittest.TestCase):
    def feed(self, **kw):
        base = {'generated_utc': '2026-11-07T19:30:00+00:00', 'date': '20261107', 'games': [1], 'errors': {}, 'counts': {}}
        base.update(kw)
        return lambda url, token=None: base

    def levels(self, findings):
        return [f[0] for f in findings]

    def test_fresh_feed_is_ok(self):
        self.assertNotIn('FAIL', self.levels(agent_audit.check_feed('https://x/', NOW, self.feed())))

    def test_stale_and_wrong_date_fail(self):
        f = agent_audit.check_feed('https://x/', NOW, self.feed(generated_utc='2026-11-07T15:00:00Z', date='20261106'))
        self.assertEqual(self.levels(f)[:2], ['FAIL', 'FAIL'])

    def test_unreachable_feed_fails(self):
        def boom(url, token=None):
            raise OSError('down')
        self.assertEqual(self.levels(agent_audit.check_feed('https://x/', NOW, boom)), ['FAIL'])

    def test_grading_flags_unsourced_and_overdue_but_not_pass(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'picks.json').write_text(json.dumps({'picks': [
                {'id': 'a', 'market': 'ft', 'game_date': '2026-11-06T00:00Z', 'grade': 'Win'},
                {'id': 'b', 'market': 'ft', 'game_date': '2026-11-06T00:00Z', 'grade': 'Pending'},
                {'id': 'c', 'market': 'pass', 'selection': 'none', 'game_date': '2026-11-06T00:00Z'},
                {'id': 'd', 'market': 'ft', 'game_date': '2026-11-07T19:00Z'}]}))
            Path(d, 'prediction_log.json').write_text(json.dumps({'predictions': []}))
            msgs = [m for lvl, a, m in agent_audit.check_grades(d, NOW) if lvl != 'OK']
        self.assertTrue(any('1 grades lack grade_source: a' in m for m in msgs))
        self.assertTrue(any('1 past-due ungraded: b' in m for m in msgs))

    def test_workflow_failure_detected(self):
        runs = {'workflow_runs': [
            {'name': 'Refresh and deploy MatchLab', 'conclusion': 'failure', 'html_url': 'u1', 'updated_at': '2026-11-07T19:50:00Z'},
            {'name': 'Refresh and deploy MatchLab', 'conclusion': 'success', 'html_url': 'u2', 'updated_at': '2026-11-07T19:20:00Z'}]}
        f = agent_audit.check_workflows(NOW, get=lambda url, token=None: runs)
        self.assertEqual(f[0][0], 'FAIL')
        self.assertEqual(agent_audit.summarize(f), 'FAIL')


class GradeNowTests(unittest.TestCase):
    def test_timestamp_only_change_is_reverted_and_new_grade_kept(self):
        with tempfile.TemporaryDirectory() as d:
            picks = {'updated_utc': 'old', 'picks': [{'id': 'p1', 'grade': None}]}
            log = {'updated_utc': 'old', 'predictions': [{'key': 'k1', 'grade': None}]}
            Path(d, 'picks.json').write_text(json.dumps(picks))
            Path(d, 'prediction_log.json').write_text(json.dumps(log))
            original_log = Path(d, 'prediction_log.json').read_bytes()

            def fake_grade(data, now):
                p = json.loads(Path(data, 'picks.json').read_text()); p['updated_utc'] = 'new'; p['picks'][0]['grade'] = 'Win'
                Path(data, 'picks.json').write_text(json.dumps(p))
                q = json.loads(Path(data, 'prediction_log.json').read_text()); q['updated_utc'] = 'new'
                Path(data, 'prediction_log.json').write_text(json.dumps(q))
            with mock.patch.object(grade_now, 'grade_files', fake_grade):
                changed = grade_now.main(d, NOW)
            self.assertEqual(changed, [('picks.json', 'p1', 'Win')])
            self.assertEqual(Path(d, 'prediction_log.json').read_bytes(), original_log)

    def test_dropped_record_aborts(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'picks.json').write_text(json.dumps({'picks': [{'id': 'p1'}]}))
            with mock.patch.object(grade_now, 'grade_files', lambda data, now: Path(data, 'picks.json').write_text('{"picks": []}')):
                with self.assertRaises(SystemExit):
                    grade_now.main(d, NOW)


if __name__ == '__main__':
    unittest.main()
