import unittest,math
from models import soccer_predict,soccer_backtest,nba_estimate,nba_backtest,metrics,temperature
class ModelsTest(unittest.TestCase):
    def soccer(self):return [{'date':f'2026-{1+i//28:02}-{1+i%28:02}','home':'a','away':'b','h':i%3,'a':i%2} for i in range(90)]
    def nba(self):return [{'date':f'2026-{1+i//28:02}-{1+i%28:02}','minutes':30,'rebounds':i%10} for i in range(70)]
    def test_soccer_normalizes_with_draw(self):
        p=soccer_predict(self.soccer(),'a','b','2026-04-01');self.assertAlmostEqual(sum(p['probabilities'].values()),1);self.assertGreater(p['probabilities']['draw'],0)
    def test_future_labels_do_not_affect_prediction(self):
        r=self.soccer();a=soccer_predict(r,'a','b','2026-03-01');r.append({'date':'2026-03-10','home':'a','away':'b','h':12,'a':0});b=soccer_predict(r,'a','b','2026-03-01');self.assertEqual(a,b)
    def test_soccer_split_order(self):
        b=soccer_backtest(self.soccer());self.assertLess(b['validation_start'],b['test_start']);self.assertGreater(b['test']['n'],0)
    def test_missing_history_no_prediction(self):self.assertIsNone(soccer_predict([],'a','b','2026-01-01'))
    def test_nplus_is_inclusive(self):
        r=[{'date':f'2026-01-{i+1:02}','minutes':30,'rebounds':6} for i in range(15)];p=nba_estimate(r,'rebounds',6,'2026-02-01');self.assertEqual(p['hits'],15)
    def test_dnp_excluded_not_zero(self):
        r=self.nba();r.append({'date':'2026-03-20','minutes':0,'rebounds':0});p=nba_estimate(r,'rebounds',6,'2026-04-01');self.assertEqual(p['sample'],20);self.assertEqual(p['avg_minutes_sample'],30)
    def test_nba_no_current_game_leak(self):
        r=self.nba();p=nba_estimate(r,'rebounds',6,'2026-02-01');r=[dict(x,rebounds=100) if x['date']>='2026-02-01' else x for x in r];self.assertEqual(p,nba_estimate(r,'rebounds',6,'2026-02-01'))
    def test_nba_backtest(self):self.assertGreater(nba_backtest(self.nba(),'rebounds',6)['test']['n'],0)
    def test_perfect_metrics(self):self.assertEqual(metrics([([1,0,0],0)])['brier'],0)
    def test_temperature(self):self.assertAlmostEqual(sum(temperature([.2,.3,.5],1.5)),1)
if __name__=='__main__':unittest.main()
