import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from research import normalize_event
from build_feed import build

def event(period=1, state='in', completed=False, lines=(1,0)):
    return {'id':'1','date':'2026-11-05T20:00Z','status':{'period':period,'type':{'state':state,'completed':completed,'name':'STATUS_FINAL' if completed else 'STATUS_IN_PROGRESS'}},'competitions':[{'competitors':[{'homeAway':side,'team':{'id':side,'displayName':side},'score':str(score),'linescores':[] if score is None else [{'value':score}]} for side,score in zip(['home','away'],lines)]}]}
class ResearchTests(unittest.TestCase):
    def test_first_half_in_progress_not_settled(self):
        self.assertIsNone(normalize_event(event(), 'epl')['halftime'])
    def test_draw_is_explicit(self):
        self.assertEqual(normalize_event(event(2,lines=(0,0)),'epl')['halftime']['result'],'draw')
    def test_missing_halftime_is_unknown(self):
        self.assertIsNone(normalize_event(event(2,lines=(None,0)),'epl')['halftime'])
    def test_away_halftime_result(self):
        self.assertEqual(normalize_event(event(2,lines=(0,2)),'epl')['halftime']['result'],'away')
    def test_nba_has_no_soccer_halftime_result(self):
        self.assertIsNone(normalize_event(event(4,completed=True),'nba')['halftime'])
    def test_pregame_score_is_unknown(self):
        self.assertIsNone(normalize_event(event(state='pre'),'nba')['home']['score'])
    def test_total_failure_preserves_feed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'latest.json';p.write_text('previous')
            with patch('build_feed.scoreboard',side_effect=OSError('offline')):
                with self.assertRaises(RuntimeError): build('20261105',['nba'],p)
            self.assertEqual(p.read_text(),'previous')
    def test_partial_and_zero_games_are_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('build_feed.scoreboard',side_effect=[[],OSError('offline')]):
                f=build('20261105',['nba','epl'],Path(d)/'f.json')
            self.assertEqual(f['status'],'partial');self.assertEqual(f['counts'],{'nba':0});self.assertIn('epl',f['errors'])
if __name__=='__main__':unittest.main()
