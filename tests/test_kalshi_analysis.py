import unittest
from datetime import datetime, timezone

from kalshi_analysis import analyze


NOW = datetime(2026, 11, 13, 20, tzinfo=timezone.utc)


def snapshot(**changes):
    result = {
        'ticker': 'TEST-EVENT-YES', 'side': 'yes',
        'observed_utc': NOW.isoformat(),
        'market': {'ticker': 'TEST-EVENT-YES', 'market_type': 'binary',
                   'status': 'active', 'close_time': '2026-11-14T20:00:00Z'},
        'orderbook': {'yes_dollars': [['0.40', '100']],
                      'no_dollars': [['0.55', '100']]},
        'fee_schedule': {'status': 'estimated', 'fee_type': 'quadratic',
                         'fee_multiplier': '1'},
    }
    result.update(changes)
    return result


class AnalysisTests(unittest.TestCase):
    def test_buy_at_ask_sell_at_bid_and_charge_both_fees(self):
        a = analyze(snapshot(), contracts=10, targets=['0.75'], now=NOW)
        self.assertEqual(a['quote']['ask'], '0.45')
        self.assertEqual(a['quote']['bid'], '0.40')
        self.assertEqual(a['entry_cost'], '4.50')
        self.assertEqual(a['entry_fee_estimate'], '0.18')
        self.assertEqual(a['total_cost'], '4.68')
        self.assertEqual(a['immediate_exit_profit'], '-0.85')
        self.assertEqual(a['max_loss'], '4.68')
        self.assertEqual(a['winning_profit_ceiling'], '5.32')
        self.assertEqual(a['scenarios'][0]['net_profit'], '2.68')
        self.assertIsNone(a['expected_profit'])
        self.assertIn('independent probability', a['edge_status'].lower())

    def test_no_side_uses_complement_of_yes_bid_for_ask(self):
        a = analyze(snapshot(side='no'), now=NOW)
        self.assertEqual(a['quote']['ask'], '0.60')
        self.assertEqual(a['quote']['bid'], '0.55')

    def test_walks_depth_instead_of_inventing_top_price_fill(self):
        s = snapshot(orderbook={'yes_dollars': [['0.40', '100']],
                               'no_dollars': [['0.50', '8'], ['0.55', '2']]})
        a = analyze(s, contracts=10, now=NOW)
        self.assertEqual(a['entry_cost'], '4.90')
        self.assertEqual(a['average_entry_price'], '0.49')

    def test_budget_includes_fees(self):
        a = analyze(snapshot(), budget='4.60', now=NOW)
        self.assertEqual(a['contracts'], 9)
        self.assertLessEqual(float(a['total_cost']), 4.60)

    def test_subcent_notional_rounding_is_included(self):
        s = snapshot(orderbook={'yes_dollars': [['0.04', '100']],
                               'no_dollars': [['0.945', '100']]})
        a = analyze(s, contracts=1, now=NOW)
        self.assertEqual(a['total_cost'], '0.06')
        self.assertEqual(a['entry_fee_estimate'], '0.005')

    def test_missing_fee_schedule_suppresses_net_claims(self):
        a = analyze(snapshot(fee_schedule={'status': 'unavailable'}), now=NOW)
        self.assertIsNone(a['winning_profit_ceiling'])
        self.assertIsNone(a['scenarios'][0]['net_profit'])
        self.assertIn('fee', ' '.join(a['blockers']).lower())

    def test_partial_book_does_not_claim_all_contracts_are_executable(self):
        s = snapshot(orderbook={'yes_dollars': [['0.40', '100']],
                               'no_dollars': [['0.55', '2']]})
        a = analyze(s, contracts=10, now=NOW)
        self.assertIn('depth', ' '.join(a['blockers']).lower())
        self.assertIsNone(a['entry_cost'])

    def test_zero_bid_is_preserved_and_no_exit_liquidity_is_explicit(self):
        s = snapshot(orderbook={'yes_dollars': [['0', '100']],
                               'no_dollars': [['0.55', '100']]})
        a = analyze(s, now=NOW)
        self.assertEqual(a['quote']['bid'], '0')
        self.assertEqual(a['immediate_exit_profit'], '-4.68')
        empty = analyze(snapshot(orderbook={'yes_dollars': [], 'no_dollars': [['0.55', '100']]}), now=NOW)
        self.assertIsNone(empty['immediate_exit_profit'])
        self.assertIn('exit', ' '.join(empty['blockers']).lower())

    def test_stale_closed_and_scalar_block_entry(self):
        for changes in [
            {'observed_utc': '2026-11-13T19:57:59Z'},
            {'observed_utc': '2026-11-13T20:01:00Z'},
            {'market': {'market_type': 'binary', 'status': 'closed'}},
            {'market': {'market_type': 'scalar', 'status': 'active'}},
            {'market': {'market_type': 'binary', 'status': 'active', 'close_time': '2026-11-13T19:59:00Z'}},
        ]:
            with self.subTest(changes=changes):
                a = analyze(snapshot(**changes), now=NOW)
                self.assertTrue(a['blockers'])
                self.assertIsNone(a['expected_profit'])

    def test_crossed_book_and_invalid_levels_block_assessment(self):
        for book in [
            {'yes_dollars': [['0.60', '10']], 'no_dollars': [['0.55', '10']]},
            {'yes_dollars': [['NaN', '10']], 'no_dollars': [['0.55', '10']]},
            {'yes_dollars': [['0.4', '-10']], 'no_dollars': [['0.55', '10']]},
        ]:
            a = analyze(snapshot(orderbook=book), now=NOW)
            self.assertTrue(a['blockers'])
            self.assertIsNone(a['entry_cost'])

    def test_probability_requires_provenance_and_never_means_peak_forecast(self):
        with self.assertRaises(ValueError):
            analyze(snapshot(), probability='0.65', now=NOW)
        a = analyze(snapshot(), probability='0.65', probability_source='User hypothetical estimate', now=NOW)
        self.assertEqual(a['expected_profit'], '1.82')
        self.assertIsNone(a['future_peak_price'])
        self.assertIn('hypothetical', a['edge_status'].lower())

    def test_rejects_bad_inputs(self):
        for kwargs in [{'contracts': 0}, {'contracts': 1.5}, {'budget': 'NaN'},
                       {'probability': '1.1', 'probability_source': 'test'},
                       {'targets': ['2']}, {'contracts': True}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                analyze(snapshot(), now=NOW, **kwargs)

    def test_nonstandard_payout_and_malformed_containers_are_blocked(self):
        for market in [
            {'market_type': 'binary', 'status': 'active', 'notional_value_dollars': '0.50'},
            {'market_type': 'binary', 'status': 'active', 'settlement_bounds_type': 'custom'},
            {'market_type': 'binary', 'status': 'active', 'settlement_floor_dollars': '0.20'},
            ['malformed'],
        ]:
            with self.subTest(market=market):
                a = analyze(snapshot(market=market), now=NOW)
                self.assertTrue(a['blockers'])
                self.assertIsNone(a['winning_profit_ceiling'])
        a = analyze(snapshot(fee_schedule=['malformed']), now=NOW)
        self.assertIsNone(a['total_cost'])

    def test_rounding_accumulator_carries_rebates_across_book_levels(self):
        from decimal import Decimal
        asks = [Decimal('0.4000') + Decimal(i) / 10000 for i in range(100)]
        book = {'yes_dollars': [['0.39', '100']],
                'no_dollars': [[str(1 - price), '1'] for price in asks]}
        a = analyze(snapshot(orderbook=book), contracts=100, now=NOW)
        self.assertEqual(a['total_cost'], '42.19')
        sized = analyze(snapshot(orderbook=book), budget='42.20', now=NOW)
        self.assertEqual(sized['contracts'], 100)


if __name__ == '__main__':
    unittest.main()
