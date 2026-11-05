import unittest
from odds import price,normalize_odds
class OddsTests(unittest.TestCase):
    def test_american_positive(self):self.assertAlmostEqual(price(200)['decimal'],3);self.assertAlmostEqual(price(200)['implied_probability'],1/3)
    def test_american_negative(self):self.assertAlmostEqual(price(-200)['decimal'],1.5)
    def test_missing_not_even_money(self):
        for v in [None,'',0,True,50,'nan',float('inf')]:self.assertIsNone(price(v))
    def test_period_and_provenance(self):
        f=normalize_odds({'pickcenter':[{'provider':{'name':'Book'},'homeTeamOdds':{'moneyLine':-110},'awayTeamOdds':{'moneyLine':100}}]},'now','url')[0]
        self.assertEqual(f['period'],'full_game');self.assertIsNone(f['source_quote_utc']);self.assertEqual(f['observed_utc'],'now');self.assertNotIn('1h',f['markets'])
    def test_unknown_book_withheld(self):self.assertEqual(normalize_odds({'pickcenter':[{'homeTeamOdds':{'moneyLine':100}}]},'now','url'),[])
    def test_spread_pair(self):
        f=normalize_odds({'pickcenter':[{'provider':{'name':'Book'},'pointSpread':{'home':{'close':{'line':'-7.5','odds':'-106'}},'away':{'close':{'line':'+7.5','odds':'-114'}}}}]},'now','url')[0];self.assertEqual(f['markets']['spread']['away']['line'],7.5)
    def test_missing_total_prices_not_invented(self):self.assertEqual(normalize_odds({'pickcenter':[{'provider':{'name':'Book'},'overUnder':200}]},'now','url'),[])
if __name__=='__main__':unittest.main()
