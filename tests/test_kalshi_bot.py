import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kalshi_bot import link_pick, refresh, signature


NOW = datetime(2026, 11, 13, 20, tzinfo=timezone.utc)


class Client:
    def __init__(self, bid='0.40', fail=False):
        self.bid, self.fail = bid, fail

    def get_market(self, ticker):
        if self.fail:
            raise RuntimeError('source offline')
        return {'ticker': ticker, 'event_ticker': 'TEST-EVENT', 'market_type': 'binary',
                'title': 'Test confirmed contract', 'status': 'active',
                'rules_primary': 'Exact test rules', 'close_time': '2026-11-14T20:00:00Z'}

    def get_orderbook(self, ticker):
        return {'yes_dollars': [[self.bid, '100']], 'no_dollars': [['0.55', '100']]}

    def get_fee_schedule(self, market):
        return {'status': 'estimated', 'fee_type': 'quadratic', 'fee_multiplier': '1'}


class BotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.picks = {'schema_version': 1, 'picks': [
            {'id': 'p1', 'label': 'Team 1 winner', 'league': 'nba', 'game_id': '123',
             'game_date': '2026-11-14T01:00:00Z', 'market': 'ft', 'selection': 'home', 'grade': 'Pending'},
            {'id': 'skip', 'label': 'PASS', 'market': 'pass'},
        ]}
        self.write('picks.json', self.picks)
        self.write('prediction_log.json', {'schema_version': 1, 'predictions': [{'key': 'untouched'}]})
        self.write('kalshi_watchlist.json', {'schema_version': 1, 'links': []})

    def write(self, name, obj):
        (self.data / name).write_text(json.dumps(obj), encoding='utf-8')

    def link(self):
        return link_pick(self.data, 'p1', 'TEST-EVENT-YES', 'yes', 'Confirmed exact full-game team and settlement rules', Client(), NOW)

    def test_empty_watchlist_lists_unlinked_and_never_invents_quotes(self):
        r = refresh(self.data, Client(), NOW)
        self.assertEqual(r['markets'], [])
        self.assertEqual([x['pick_id'] for x in r['unlinked_picks']], ['p1'])
        self.assertFalse((self.data / 'kalshi_observations.jsonl').exists())

    def test_link_verifies_contract_and_preserves_original_pick_and_model_bytes(self):
        original = {f: (self.data / f).read_bytes() for f in ['picks.json', 'prediction_log.json']}
        link = self.link()
        self.assertEqual(link['pick_signature'], signature(self.picks['picks'][0]))
        r = refresh(self.data, Client(), NOW)
        self.assertEqual(r['markets'][0]['assessment']['entry_cost'], '4.50')
        for f, content in original.items():
            self.assertEqual((self.data / f).read_bytes(), content)

    def test_refresh_appends_and_retains_sampled_high(self):
        self.link()
        refresh(self.data, Client(bid='0.44'), NOW)
        first = (self.data / 'kalshi_observations.jsonl').read_bytes()
        r = refresh(self.data, Client(bid='0.40'), NOW + timedelta(minutes=1))
        self.assertTrue((self.data / 'kalshi_observations.jsonl').read_bytes().startswith(first))
        self.assertEqual(r['markets'][0]['history']['high_bid'], '0.44')
        self.assertEqual(r['markets'][0]['history']['samples'], 2)

    def test_failed_refresh_preserves_last_observation_timestamp_and_archive(self):
        self.link()
        refresh(self.data, Client(), NOW)
        archive = (self.data / 'kalshi_observations.jsonl').read_bytes()
        r = refresh(self.data, Client(fail=True), NOW + timedelta(minutes=5))
        self.assertEqual(r['status'], 'partial')
        self.assertTrue(r['errors'])
        self.assertEqual(r['markets'][0]['observed_utc'], NOW.isoformat())
        self.assertIn('stale', ' '.join(r['markets'][0]['assessment']['blockers']).lower())
        self.assertEqual((self.data / 'kalshi_observations.jsonl').read_bytes(), archive)

    def test_changed_selection_requires_new_confirmation(self):
        self.link()
        self.picks['picks'][0]['selection'] = 'away'
        self.write('picks.json', self.picks)
        r = refresh(self.data, Client(), NOW)
        self.assertEqual(r['markets'], [])
        self.assertIn('changed', ' '.join(r['errors']).lower())

    def test_link_rejects_missing_pass_empty_confirmation_duplicate_and_nonbinary(self):
        for pick, note in [('missing', 'confirmed'), ('skip', 'confirmed'), ('p1', '')]:
            with self.subTest(pick=pick, note=note), self.assertRaises(ValueError):
                link_pick(self.data, pick, 'TEST-EVENT-YES', 'yes', note, Client(), NOW)
        self.link()
        with self.assertRaises(ValueError):
            self.link()

    def test_duplicate_source_ids_fail_without_replacing_current_feed(self):
        refresh(self.data, Client(), NOW)
        old = (self.data / 'kalshi.json').read_bytes()
        self.picks['picks'].append(self.picks['picks'][0])
        self.write('picks.json', self.picks)
        with self.assertRaises(ValueError):
            refresh(self.data, Client(), NOW)
        self.assertEqual((self.data / 'kalshi.json').read_bytes(), old)

    def test_link_capacity_failure_keeps_valid_configuration(self):
        self.link()
        obj = json.loads((self.data / 'kalshi_watchlist.json').read_text())
        base = obj['links'][0]
        obj['links'] = [dict(base, pick_id='existing-' + str(i)) for i in range(100)]
        self.write('kalshi_watchlist.json', obj)
        before = (self.data / 'kalshi_watchlist.json').read_bytes()
        with self.assertRaises(ValueError):
            self.link()
        self.assertEqual((self.data / 'kalshi_watchlist.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
