"""Read-only binary-contract scenarios. Prices are dollars; no peak is predicted."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR

CENT = Decimal('0.01')
MICRO = Decimal('0.000001')
ONE = Decimal(1)
MAX_CONTRACTS = 1_000_000
FEE_TYPES = {'quadratic', 'quadratic_with_maker_fees', 'quadratic_with_combo_maker_fees'}


def number(value):
    if isinstance(value, bool):
        raise ValueError('Expected a finite decimal number')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Expected a finite decimal number') from None
    if not result.is_finite():
        raise ValueError('Expected a finite decimal number')
    return result


def stamp(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp requires timezone')
    return parsed.astimezone(timezone.utc)


def text(value):
    return None if value is None else format(value, 'f')


def levels(book, key):
    raw = book.get(key)
    if not isinstance(raw, list):
        raise ValueError('Missing orderbook side')
    aggregated = {}
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError('Malformed orderbook level')
        price, quantity = map(number, row)
        if not 0 <= price <= 1 or quantity <= 0:
            raise ValueError('Invalid orderbook price or depth')
        aggregated[price] = aggregated.get(price, Decimal(0)) + quantity
    return sorted(aggregated.items(), reverse=True)


def walk(rows, quantity):
    """Full depth-weighted fill or None. Never claim a partial fill is complete."""
    remaining = Decimal(quantity)
    fills = []
    for price, available in rows:
        take = min(available, remaining)
        if take > 0:
            fills.append((price, take))
            remaining -= take
        if remaining == 0:
            return fills
    return None


def fill_fee(price, quantity, multiplier, action):
    """Non-direct single-fill taker estimate, including subcent notional alignment."""
    notional = price * quantity
    fee = (Decimal('0.07') * multiplier * quantity * price * (ONE - price)).quantize(MICRO, rounding=ROUND_CEILING)
    if action == 'buy':
        return (notional + fee).quantize(CENT, rounding=ROUND_CEILING) - notional
    return notional - (notional - fee).quantize(CENT, rounding=ROUND_FLOOR)


def cost(fills):
    return sum((p * q for p, q in fills), Decimal(0))


def fees(fills, multiplier, action):
    accumulator, total = Decimal(0), Decimal(0)
    for price, quantity in fills:
        model_fee = (Decimal('0.07') * multiplier * quantity * price * (ONE - price)).quantize(MICRO, rounding=ROUND_CEILING)
        aligned_fee = fill_fee(price, quantity, multiplier, action)
        accumulator += aligned_fee - model_fee
        rebate = min(accumulator.quantize(CENT, rounding=ROUND_FLOOR),
                     aligned_fee.quantize(CENT, rounding=ROUND_FLOOR))
        accumulator -= rebate
        total += aligned_fee - rebate
    return total


def analyze(snapshot, contracts=10, budget=None, probability=None,
            probability_source=None, targets=None, now=None):
    """Return JSON-safe scenario math and explicit reasons an entry cannot be assessed.

    Caller supplies a verified binary market, orderbook and current fee schedule.
    Probabilities are independent user scenarios, never inferred from market price.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(snapshot, dict):
        raise ValueError('Snapshot must be an object')
    quantity = number(contracts)
    if quantity != quantity.to_integral_value() or not 1 <= quantity <= MAX_CONTRACTS:
        raise ValueError('Contracts must be a whole number from 1 to 1000000')
    q = int(quantity)
    spend = number(budget) if budget is not None else None
    if spend is not None and spend <= 0:
        raise ValueError('Budget must be positive')
    p = number(probability) if probability is not None else None
    if p is not None and (not 0 <= p <= 1 or not isinstance(probability_source, str) or not probability_source.strip()):
        raise ValueError('Probability needs a value from 0 to 1 and an independent source/assumption')
    exits = [number(x) for x in (targets if targets is not None else ['0.25', '0.50', '0.75', '0.90'])]
    if any(not 0 <= x <= 1 for x in exits):
        raise ValueError('Hypothetical exit prices must be between 0 and 1')
    side = snapshot.get('side')
    if side not in ('yes', 'no'):
        raise ValueError('Side must be yes or no')
    blockers = []
    market = snapshot.get('market') if isinstance(snapshot.get('market'), dict) else {}
    is_binary = market.get('market_type') == 'binary'
    try:
        is_binary = is_binary and number(market.get('notional_value_dollars', '1')) == 1 and number(market.get('settlement_floor_dollars') or '0') == 0 and market.get('settlement_bounds_type') in (None, 'default')
    except ValueError:
        is_binary = False
    if not is_binary:
        blockers.append('Unsupported payout structure; only standard $1 binary contracts are assessed')
    if market.get('status') not in ('active', 'open'):
        blockers.append('Market is not open for entry')
    try:
        age = (now - stamp(snapshot.get('observed_utc'))).total_seconds()
        if not 0 <= age <= 120:
            blockers.append('Quote is stale or future-dated; refresh required')
    except (ValueError, TypeError, OverflowError):
        blockers.append('Quote timestamp unavailable; refresh required')
    try:
        if stamp(market.get('close_time')) <= now:
            blockers.append('Market close time has passed')
    except (ValueError, TypeError, OverflowError):
        blockers.append('Market close time unavailable')

    multiplier = None
    schedule = snapshot.get('fee_schedule') if isinstance(snapshot.get('fee_schedule'), dict) else {}
    try:
        if schedule.get('status') == 'estimated' and schedule.get('fee_type') in FEE_TYPES:
            multiplier = number(schedule.get('fee_multiplier'))
            if multiplier < 0:
                multiplier = None
    except ValueError:
        pass
    if multiplier is None:
        blockers.append('Fee schedule unavailable; net profit cannot be estimated')

    bids, asks, invalid_book = [], [], False
    try:
        book = snapshot.get('orderbook') or {}
        bids = levels(book, side + '_dollars')
        opposing = levels(book, ('no' if side == 'yes' else 'yes') + '_dollars')
        asks = [(ONE - price, quantity) for price, quantity in opposing]
        if bids and asks and bids[0][0] > asks[0][0]:
            raise ValueError('Crossed orderbook')
    except (ValueError, AttributeError):
        invalid_book = True
        blockers.append('Invalid or crossed orderbook; quote cannot be assessed')
    bid = bids[0][0] if bids and not invalid_book else None
    ask = asks[0][0] if asks and not invalid_book else None
    if ask is None or ask <= 0 or ask >= 1:
        blockers.append('No usable entry ask')
    if bid is None:
        blockers.append('No exit bids; immediate exit liquidity unavailable')

    if spend is not None and asks and multiplier is not None and not invalid_book:
        low, high = 0, min(MAX_CONTRACTS, int(sum((x[1] for x in asks), Decimal(0))))
        while low < high:
            mid = (low + high + 1) // 2
            filled = walk(asks, mid)
            if filled and cost(filled) + fees(filled, multiplier, 'buy') <= spend:
                low = mid
            else:
                high = mid - 1
        q = low
        if not q:
            blockers.append('Budget cannot cover one contract including estimated fees')
    elif spend is not None:
        q = 0
        blockers.append('Budget sizing unavailable without a usable book and fee schedule')

    entry = walk(asks, q) if q and not invalid_book and ask is not None and 0 < ask < 1 and is_binary else None
    exit_fills = walk(bids, q) if q and not invalid_book else None
    if entry is None:
        blockers.append('Insufficient entry depth for the requested contract count')
    if exit_fills is None and bid is not None:
        blockers.append('Insufficient exit depth for the requested contract count')
    entry_cost = cost(entry) if entry is not None else None
    entry_fee = fees(entry, multiplier, 'buy') if entry is not None and multiplier is not None else None
    total = (entry_cost + entry_fee).quantize(CENT) if entry_fee is not None else None
    immediate = cost(exit_fills) - fees(exit_fills, multiplier, 'sell') - total if exit_fills is not None and total is not None else None
    scenarios = []
    for target in exits:
        net = Decimal(q) * target - fill_fee(target, Decimal(q), multiplier, 'sell') - total if total is not None else None
        scenarios.append({'exit_price': text(target), 'net_profit': text(net),
                          'roi_pct': text((net / total * 100).quantize(Decimal('0.01'))) if net is not None and total else None})
    breakeven = None
    if total is not None:
        # A hypothetical threshold, not a valid-tick limit order or a fill promise.
        low, high = 0, 10000
        while low < high:
            mid = (low + high) // 2
            candidate = Decimal(mid) / 10000
            if Decimal(q) * candidate - fill_fee(candidate, Decimal(q), multiplier, 'sell') >= total:
                high = mid
            else:
                low = mid + 1
        candidate = Decimal(low) / 10000
        if Decimal(q) * candidate - fill_fee(candidate, Decimal(q), multiplier, 'sell') >= total:
            breakeven = candidate
    expected = Decimal(q) * p - total if p is not None and total is not None and not blockers else None
    return {
        'status': 'BLOCKED / SNAPSHOT ONLY' if blockers else 'RESEARCH ONLY',
        'blockers': blockers, 'contracts': q,
        'quote': {'bid': text(bid), 'ask': text(ask), 'spread': text(ask - bid) if ask is not None and bid is not None else None},
        'average_entry_price': text((entry_cost / q).normalize()) if entry_cost is not None else None,
        'entry_cost': text(entry_cost), 'entry_fee_estimate': text(entry_fee),
        'total_cost': text(total), 'max_loss': text(total),
        'winning_profit_ceiling': text(Decimal(q) - total) if total is not None and is_binary else None,
        'immediate_exit_profit': text(immediate), 'breakeven_exit': text(breakeven),
        'scenarios': scenarios, 'expected_profit': text(expected),
        'probability': text(p), 'probability_source': probability_source,
        'edge_status': 'Hypothetical expected value using the supplied independent probability; no verified edge established' if p is not None else 'Insufficient evidence: supply an independent probability and its source to estimate expected value',
        'future_peak_price': None,
        'fee_note': 'Estimated taker fees with non-direct member cent balance alignment and per-order rounding rebates, assuming one fill per visible price level. Actual split fills, member rounding, waivers, fee changes and slippage may differ. Future exits assume the current schedule. Winning binary settlement has no trading exit fee.',
        'scenario_note': 'Exit prices are hypothetical; no likelihood of reaching them is assigned. The winning settlement ceiling is mathematical, not a future peak forecast. Maximum loss assumes buying a fully funded binary contract.',
    }
