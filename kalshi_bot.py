"""One-shot public Kalshi research tracker. No orders, accounts or wager writes."""
import argparse
import hashlib
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from kalshi_analysis import analyze, number, stamp
from kalshi_api import KalshiClient, KalshiError

ROOT = Path(__file__).resolve().parent
BASE = 'https://external-api.kalshi.com/trade-api/v2'
IDENTITY_FIELDS = ('id', 'league', 'game_id', 'game_date', 'market', 'selection',
                   'player_id', 'stat', 'threshold', 'line')


def load(path, default=None):
    if not path.exists() and default is not None:
        return default
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON number')))


def write(path, value):
    """Atomic replacement for derived feeds/configuration; history uses append only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False, suffix='.tmp') as f:
        tmp = Path(f.name)
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')
    try:
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def signature(pick):
    identity = {k: pick.get(k) for k in IDENTITY_FIELDS}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()


def picks_by_id(data):
    document = load(data / 'picks.json')
    if not isinstance(document, dict) or document.get('schema_version') != 1 or not isinstance(document.get('picks'), list):
        raise ValueError('Invalid editorial picks schema')
    rows = {}
    for row in document['picks']:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'] or row['id'] in rows:
            raise ValueError('Missing or duplicate editorial pick ID')
        rows[row['id']] = row
    return rows


def watchlist(data):
    obj = load(data / 'kalshi_watchlist.json', {'schema_version': 1, 'links': []})
    if not isinstance(obj, dict) or obj.get('schema_version') != 1 or not isinstance(obj.get('links'), list):
        raise ValueError('Invalid Kalshi watchlist schema')
    seen = set()
    for row in obj['links']:
        if not isinstance(row, dict) or row.get('side') not in ('yes', 'no') or not all(isinstance(row.get(k), str) and row[k].strip() for k in ('pick_id', 'ticker', 'confirmed_utc', 'match_note', 'pick_signature')):
            raise ValueError('Each Kalshi link needs a pick ID, ticker, side, confirmation time, exact-match note and selection fingerprint')
        stamp(row['confirmed_utc'])
        if row['pick_id'] in seen:
            raise ValueError('Duplicate Kalshi pick link')
        seen.add(row['pick_id'])
    if len(seen) > 100:
        raise ValueError('Watchlist exceeds 100 contracts; split the workload explicitly')
    return obj


def link_pick(data, pick_id, ticker, side, match_note, client=None, now=None):
    """Record an explicit contract equivalence assertion, never a fuzzy match."""
    data = Path(data)
    now = now or datetime.now(timezone.utc)
    if side not in ('yes', 'no') or not isinstance(match_note, str) or not match_note.strip():
        raise ValueError('Specify yes/no and a confirmation of event, period, participant, threshold and rules')
    picks = picks_by_id(data)
    pick = picks.get(pick_id)
    if not pick or pick.get('market') == 'pass' or str(pick.get('selection', '')).lower() == 'pass':
        raise ValueError('Link an existing non-PASS editorial pick ID')
    config = watchlist(data)
    if any(x['pick_id'] == pick_id for x in config['links']):
        raise ValueError('Pick already linked; preserve its existing confirmation and tracking history')
    if len(config['links']) >= 100:
        raise ValueError('Watchlist already contains 100 contracts; existing configuration retained')
    market = (client or KalshiClient()).get_market(ticker)
    if market.get('ticker') != ticker or market.get('market_type') != 'binary':
        raise ValueError('An exact verified binary Kalshi contract is required')
    row = {'pick_id': pick_id, 'ticker': ticker, 'side': side,
           'confirmed_utc': now.isoformat(), 'match_note': match_note.strip(),
           'pick_signature': signature(pick)}
    config['links'].append(row)
    write(data / 'kalshi_watchlist.json', config)
    return row


def key(link):
    return ':'.join(link[x] for x in ('pick_id', 'ticker', 'side', 'pick_signature'))


def archive_rows(path):
    histories = {}
    if path.exists():
        with path.open(encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if row.get('schema_version') != 1 or not isinstance(row.get('link_key'), str):
                        raise ValueError('Invalid observation schema')
                    stamp(row['observed_utc'])
                    histories.setdefault(row['link_key'], []).append(row)
                except (ValueError, KeyError, AttributeError) as error:
                    raise ValueError(f'Invalid Kalshi observation at line {line_no}; archive retained') from error
    return histories


def fetch_snapshot(ticker, side, client, now):
    market = client.get_market(ticker)
    if market.get('ticker') != ticker:
        raise ValueError('Provider returned a different market ticker')
    book = client.get_orderbook(ticker)
    # Record collection completion, rather than a pre-request time, in live use.
    observed = now or datetime.now(timezone.utc)
    return {'ticker': ticker, 'side': side, 'market': market, 'orderbook': book,
            'fee_schedule': client.get_fee_schedule(market), 'observed_utc': observed.isoformat(),
            'source_url': BASE + '/markets/' + quote(ticker, safe='')}


def history_summary(rows):
    highs, lows = [], []
    for row in rows:
        a = analyze(row, now=stamp(row['observed_utc']))
        for field, values in [('bid', highs), ('ask', lows)]:
            v = a['quote'].get(field)
            if v is not None:
                values.append(number(v))
    return {'first_observed_utc': rows[0]['observed_utc'] if rows else None,
            'samples': len(rows), 'high_bid': str(max(highs)) if highs else None,
            'low_ask': str(min(lows)) if lows else None,
            'note': 'Sampled quotes since linking, not an all-time high or a forecast. Snapshot highs do not guarantee executable size.'}


def refresh(data=None, client=None, now=None):
    data = Path(data) if data is not None else ROOT / 'data'
    client = client or KalshiClient()
    fixed_now = now
    now = now or datetime.now(timezone.utc)
    picks = picks_by_id(data)
    config = watchlist(data)
    archive = data / 'kalshi_observations.jsonl'
    histories = archive_rows(archive)
    report = {'schema_version': 1, 'generated_utc': now.isoformat(), 'status': 'ok',
              'errors': [], 'markets': [], 'unlinked_picks': [],
              'disclaimer': 'Read-only research. Sampled highs describe past quotes. Future peak prices and target probabilities are unknown. No wagers are placed.'}
    linked = set()
    fetched = {}
    started = time.monotonic()
    for link in config['links']:
        pick = picks.get(link['pick_id'])
        if not pick or pick.get('market') == 'pass' or signature(pick) != link['pick_signature']:
            report['errors'].append(link['pick_id'] + ': pick missing or selection changed; exact contract confirmation required')
            continue
        linked.add(link['pick_id'])
        link_key = key(link)
        rows = histories.setdefault(link_key, [])
        try:
            if time.monotonic() - started > 180:
                raise KalshiError('Refresh time budget reached; previous observation retained')
            if link['ticker'] not in fetched:
                fetched[link['ticker']] = fetch_snapshot(link['ticker'], link['side'], client, fixed_now)
            snapshot = dict(fetched[link['ticker']], side=link['side'])
            # Analyze before appending to reject malformed provider structures.
            analysis = analyze(snapshot, now=fixed_now or datetime.now(timezone.utc))
            if any('Invalid or crossed' in x for x in analysis['blockers']):
                raise ValueError('Invalid provider orderbook; previous observation retained')
            snapshot.update({'schema_version': 1, 'link_key': link_key, 'pick_id': link['pick_id']})
            if not rows or rows[-1]['observed_utc'] != snapshot['observed_utc']:
                archive.parent.mkdir(parents=True, exist_ok=True)
                with archive.open('a', encoding='utf-8', newline='\n') as f:
                    f.write(json.dumps(snapshot, allow_nan=False, separators=(',', ':')) + '\n')
                rows.append(snapshot)
            if snapshot['fee_schedule'].get('status') != 'estimated':
                report['errors'].append(link['ticker'] + ': fee schedule unavailable; net-profit estimates suppressed')
        except (KalshiError, ValueError, TypeError, KeyError, RuntimeError) as error:
            report['errors'].append(link['ticker'] + ': ' + str(error)[:180])
        if not rows:
            continue
        latest = rows[-1]
        assessment = analyze(latest, now=fixed_now or datetime.now(timezone.utc))
        report['markets'].append({'pick_id': link['pick_id'], 'label': pick.get('label', link['pick_id']),
                                  'ticker': link['ticker'], 'side': link['side'],
                                  'market_status': latest['market'].get('status'),
                                  'title': latest['market'].get('title'),
                                  'rules': latest['market'].get('rules_primary'),
                                  'observed_utc': latest['observed_utc'], 'source_url': latest['source_url'],
                                  'quote': assessment['quote'], 'history': history_summary(rows),
                                  'assessment': assessment})
    for pick_id, pick in picks.items():
        if pick_id not in linked and pick.get('market') != 'pass' and str(pick.get('selection', '')).lower() != 'pass':
            report['unlinked_picks'].append({'pick_id': pick_id, 'label': pick.get('label', pick_id),
                                              'league': pick.get('league'), 'game_date': pick.get('game_date'),
                                              'grade': pick.get('grade', 'Pending'),
                                              'reason': 'Exact Kalshi event, period, participant, threshold, side and rules not confirmed'})
    report['status'] = 'partial' if report['errors'] else 'ok'
    write(data / 'kalshi.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('refresh', help='Refresh linked contracts once and append public observations')
    search = sub.add_parser('search', help='List a bounded page of candidates; never links automatically')
    search.add_argument('--series', required=True)
    search.add_argument('--query', default='')
    search.add_argument('--limit', type=int, default=100)
    inspect = sub.add_parser('inspect', help='Show exact contract metadata and settlement rules')
    inspect.add_argument('ticker')
    link = sub.add_parser('link', help='Confirm an exact pick-to-contract match')
    link.add_argument('pick_id')
    link.add_argument('ticker')
    link.add_argument('--side', choices=['yes', 'no'], required=True)
    link.add_argument('--confirm-match', required=True, help='Describe verified event/period/player/threshold/rules equivalence')
    assess = sub.add_parser('assess', help='Fresh read-only analysis for a market; no forecast of its peak')
    assess.add_argument('ticker')
    assess.add_argument('--side', choices=['yes', 'no'], required=True)
    sizing = assess.add_mutually_exclusive_group()
    sizing.add_argument('--contracts', type=int, default=10)
    sizing.add_argument('--budget')
    assess.add_argument('--probability')
    assess.add_argument('--probability-source')
    assess.add_argument('--target', action='append')
    args = parser.parse_args(argv)
    try:
        client = KalshiClient()
        if args.command == 'refresh':
            result = refresh(args.data_dir, client)
        elif args.command == 'inspect':
            result = client.get_market(args.ticker)
        elif args.command == 'link':
            result = link_pick(args.data_dir, args.pick_id, args.ticker, args.side, args.confirm_match, client)
        elif args.command == 'search':
            rows = client.list_markets(series_ticker=args.series, limit=args.limit)
            result = {'note': 'Candidates only; verify exact rules before linking. One bounded page, not exhaustive.',
                      'markets': [r for r in rows if args.query.casefold() in ' '.join(str(r.get(k, '')) for k in ('title', 'subtitle', 'yes_sub_title', 'ticker')).casefold()]}
        else:
            snap = fetch_snapshot(args.ticker, args.side, client, None)
            result = {'ticker': args.ticker, 'side': args.side, 'observed_utc': snap['observed_utc'],
                      'assessment': analyze(snap, args.contracts, args.budget, args.probability, args.probability_source, args.target)}
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 1 if isinstance(result, dict) and result.get('status') == 'partial' else 0
    except (KalshiError, ValueError, OSError, KeyError) as error:
        print('Kalshi tracker: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
