import unittest
from grading import outcome
from research import normalize_event
from test_research import event

class GradingTests(unittest.TestCase):
    def summary(self, completed=True, dnp=False, stats=None):
        return {'header': {'competitions': [{'status': {'type': {'completed': completed}}, 'competitors': [
            {'homeAway': 'home', 'score': '3'}, {'homeAway': 'away', 'score': '2'}]}]},
            'boxscore': {'players': [{'statistics': [{'labels': ['PTS', 'REB', 'AST', '3PT'], 'athletes': [
                {'athlete': {'id': '1'}, 'didNotPlay': dnp, 'stats': stats or ['20', '6', '4', '3-8']}]}]}]}}
    def test_inclusive_milestone_from_final_boxscore(self):
        self.assertEqual(outcome({'market':'nplus','player_id':'1','stat':'points','threshold':20},self.summary())['grade'],'Win')
    def test_live_boxscore_never_grades(self):
        self.assertIsNone(outcome({'market':'ft','selection':'home'},self.summary(completed=False)))
    def test_dnp_is_not_a_loss(self):
        self.assertEqual(outcome({'market':'nplus','player_id':'1','stat':'points','threshold':20},self.summary(dnp=True))['grade'],'DNP')
    def test_missing_athlete_stays_unknown(self):
        self.assertIsNone(outcome({'market':'nplus','player_id':'2','stat':'points','threshold':20},self.summary()))
    def test_three_point_makes_not_attempts(self):
        self.assertEqual(outcome({'market':'nplus','player_id':'1','stat':'threes','threshold':4},self.summary())['grade'],'Loss')
    def test_nhl_final_including_overtime(self):
        self.assertEqual(outcome({'market':'ft','selection':'home'},self.summary())['grade'],'Win')
    def test_hockey_period_one_is_not_soccer_halftime(self):
        g=normalize_event(event(3,completed=True),'nhl')
        self.assertIsNone(g['halftime']);self.assertIn('/nhl/',g['source_url'])
