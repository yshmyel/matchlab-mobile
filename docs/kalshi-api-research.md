# Kalshi read-only pick tracking

Verified 2026-11-13 against official Kalshi documentation. Intended integration: collect snapshots during Match Lab's existing Pages build; no trading credentials, order endpoints, or additional recurring jobs.

## API contract

- Recommended production base: `https://external-api.kalshi.com/trade-api/v2`. Market data is public; no API key is needed. [Environments](https://docs.kalshi.com/getting_started/api_environments), [public-data guide](https://docs.kalshi.com/getting_started/quick_start_market_data).
- Verify exact markets through `GET /markets/{ticker}`. Discover candidates through `/markets?series_ticker=...&status=open` or `event_ticker`; refresh linked tickers using `tickers=A,B`. General listings use cursors, maximum page size 1,000. No general free-text query parameter is documented. Prices/status are cached and can lag; deduplicate by ticker. [Markets API](https://docs.kalshi.com/api-reference/market/get-markets).
- Preserve pick ID, explicit market ticker, YES/NO side, linkage timestamp, and mapping confirmation. Candidate title similarity is not proof of matching participants, dates, thresholds, or settlement rules; inspect `rules_primary` and `rules_secondary`. [Market schema](https://docs.kalshi.com/api-reference/events/get-event).
- Read dollar strings (`yes_bid_dollars`, `yes_ask_dollars`, corresponding NO fields, `last_price_dollars`) and quantity strings (`volume_fp`, `volume_24h_fp`, `open_interest_fp`). Use decimal arithmetic; sub-cent prices and fractional quantities exist. Dynamic `price_ranges` defines valid ticks. [Fixed-point representation](https://docs.kalshi.com/getting_started/fixed_point_migration).
- `GET /markets/{ticker}/orderbook` returns `orderbook_fp.yes_dollars` and `.no_dollars`, ascending `[dollarPrice, quantity]` pairs. YES ask is one minus best NO bid; NO ask is one minus best YES bid. Enter at asks; immediate exits use bids and available depth. Nonexistent tickers can return HTTP 200 with empty books. [Orderbook API](https://docs.kalshi.com/api-reference/market/get-market-orderbook).

## Collection and history

- Retain timestamped successful snapshots and linkage identity. A sampled high is the highest observed bid since linkage, with sample count and time coverage; a half-hour build cannot establish an intraperiod peak or current executable liquidity.
- Candles: `/series/{series}/markets/{ticker}/candlesticks`, with UNIX-second `start_ts`, `end_ts`, and `period_interval` of 1, 60, or 1440 minutes. Maximum 5,000 periods per call. Bid, ask, and trade OHLC are separate; missing trade observations may be null. [Candlesticks API](https://docs.kalshi.com/api-reference/market/get-market-candlesticks).
- `/markets/trades` supports ticker/time filters and cursor pagination; deduplicate `trade_id`. [Trades API](https://docs.kalshi.com/api-reference/market/get-trades).
- `/historical/cutoff` supplies moving `market_settled_ts` and `trades_created_ts` boundaries. Route older markets/candles to `/historical/markets` and older trades to `/historical/trades`; do not assume fixed retention days. [Historical data](https://docs.kalshi.com/getting_started/historical_data).
- Use bounded timeout/retries and exponential backoff for 429. Kalshi says 429 does not include `Retry-After`; cached public responses often omit rate-limit headers. Never mark a failed refresh as successful or silently replace missing data with zero. [Rate limits](https://docs.kalshi.com/getting_started/rate_limits).

## Fee metadata and estimates

`GET /series/{series_ticker}` provides `fee_type` and `fee_multiplier`. Supported quadratic types can use the general taker model; unsupported types such as `flat` require a separate implementation or an unavailable estimate. [Series API](https://docs.kalshi.com/api-reference/market/get-series).

`GET /events/{event_ticker}` provides nullable `event.fee_type_override` and `event.fee_multiplier_override`, which take precedence when present. Multiplier zero is valid. [Event API](https://docs.kalshi.com/api-reference/events/get-event).

`GET /events/fee_changes?event_ticker=...&limit=1000&cursor=...` returns `event_fee_changes` plus cursor. Each change includes `id`, `event_ticker`, `series_ticker`, `fee_type_override`, `fee_multiplier_override`, and `scheduled_ts`; a null override pair clears the override. [Event fee changes](https://docs.kalshi.com/api-reference/events/get-event-fee-changes). Series changes are at `/series/fee_changes?series_ticker=...&show_historical=true`. [Series fee changes](https://docs.kalshi.com/api-reference/exchange/get-series-fee-changes).

The general taker model is `0.07 * multiplier * contracts * price * (1-price)`, with product exceptions. [Current fee PDF](https://kalshi.com/docs/kalshi-fee-schedule.pdf), [fee schedule](https://kalshi.com/fee-schedule).

For a conservative **hypothetical single-fill estimate** with unknown member type, use the coarser $0.01 balance grid. Let `f = ceil_6dp(model_fee)` and `c = quantity * price`; estimate buy fees as `ceil_cent(c+f)-c` and sell fees as `c-floor_cent(c-f)`. This is an inference from documented rounding, not a guaranteed bound for unknown split fills. Label estimates accordingly; absent fee metadata cannot support exact net profit. [Rounding mechanics](https://docs.kalshi.com/getting_started/fee_rounding).

## Analysis boundaries

For standard binary contracts, a winning side pays $1 per contract; simple YES/NO settlement fees are zero. Scalar/floor products require different handling. [Settlement](https://docs.kalshi.com/getting_started/market_settlement), [settlement bounds](https://docs.kalshi.com/getting_started/settlement_bounds).

Show hypothetical exit profit as `q*(exit-entry)-entryFees-exitFees`, and maximum loss as entry cost plus entry fees. A winning settlement ceiling `q*(1-entry)-entryFees` is mathematical, not a forecast of how high prices will rise. Historical highs cannot establish future peaks. Expected settlement profit `q*(independentProbability-entry)-entryFees` requires a traceable independent probability estimate; otherwise report insufficient evidence of edge. Block actionable assessment for stale/missing quotes, unsupported payouts/fees, ambiguous mappings, closed markets, or insufficient depth.

## Browser access probe

Read-only probe on 2026-11-13: `/markets?limit=1&status=open&mve_filter=exclude` returned HTTP 200 without `Origin`, `Cache-Control: public, max-age=15`, and no `Access-Control-Allow-Origin`. An otherwise identical request with `Origin: https://matchlab.example` returned HTTP 403 and no allow-origin header. This directly observed endpoint behavior supports collecting data server-side and publishing snapshots; it does not establish every Kalshi endpoint's CORS policy.
