const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, {textContent: '', innerHTML: ''});
  return elements.get(id);
};
const context = vm.createContext({document: {getElementById: element}, Date, Intl, URL});
if (fs.existsSync('kalshi_ui.js')) vm.runInContext(fs.readFileSync('kalshi_ui.js', 'utf8'), context);
assert.equal(typeof context.renderKalshi, 'function', 'Kalshi view must expose its renderer');

const now = Date.parse('2026-11-13T18:00:00Z');
const market = {
  pick_id: 'p1', label: 'Sample player 20+ points', ticker: 'TEST-MARKET', side: 'yes',
  market_status: 'active', observed_utc: '2026-11-13T17:59:30Z',
  source_url: 'https://external-api.kalshi.com/trade-api/v2/markets/TEST-MARKET',
  quote: {bid: '0.40', ask: '0.45', spread: '0.05'},
  history: {first_observed_utc: '2026-11-13T17:00:00Z', samples: 3, high_bid: '0.50', low_ask: '0.44'},
  assessment: {status: 'WATCH', blockers: [], contracts: 10, entry_cost: '4.50',
    entry_fee_estimate: '0.18', total_cost: '4.68', max_loss: '4.68',
    winning_profit_ceiling: '5.32', immediate_exit_profit: '-0.85', breakeven_exit: '0.49',
    edge_status: 'Unknown: no verified probability', expected_profit: null,
    fee_note: 'Estimated fees; verify your applicable schedule.',
    scenarios: [{exit_price: '0.60', net_profit: '1.14', roi_pct: '24.36'}]}
};
const feed = (markets = [market], extra = {}) => ({schema_version: 1,
  generated_utc: '2026-11-13T18:00:00Z', status: 'ok', errors: [], markets,
  unlinked_picks: [], ...extra});
const render = value => context.renderKalshi(value, now);
const cards = () => element('kalshiMarkets').innerHTML;

render(feed());
assert.match(cards(), /Sample player 20\+ points/);
assert.match(cards(), /Current bid/);
assert.match(cards(), /\$0\.40/);
assert.match(cards(), /Current ask/);
assert.match(cards(), /\$0\.45/);
assert.match(cards(), /Immediate.exit/i);
assert.match(cards(), /-\$0\.85/);
assert.match(cards(), /winning settlement ceiling/i);
assert.match(cards(), /\$5\.32/);
assert.match(cards(), /Maximum loss/i);
assert.match(cards(), /\$4\.68/);
assert.match(cards(), /Hypothetical exit scenarios/i);
assert.match(cards(), /\$1\.14/);
assert.match(cards(), /24\.36%/);
assert.match(cards(), /sampled since tracking began/i);
assert.match(cards(), /3 samples/);
assert.match(cards(), /PT/);
assert.match(element('kalshiStatus').innerHTML, /future maximum.*unknown/i);

render(feed([{...market, quote: {bid: '0', ask: null, spread: null},
  assessment: {...market.assessment, immediate_exit_profit: '0', expected_profit: null}}]));
assert.match(cards(), /Current bid[\s\S]*?\$0\.00/);
assert.match(cards(), /Current ask[\s\S]*?Unavailable/);
assert.match(cards(), /Immediate.exit[\s\S]*?\$0\.00/i);
assert.doesNotMatch(cards(), /NaN|undefined/);

render(feed([{...market, observed_utc: '2026-11-13T17:30:00Z',
  assessment: {...market.assessment, status: 'ENTRY READY'}}]));
assert.match(cards(), /Snapshot \/ refresh required/);
assert.doesNotMatch(cards(), /ENTRY READY/);
assert.match(cards(), /assessment paused/i);
render(feed([{...market, observed_utc: null}]));
assert.match(cards(), /Snapshot \/ refresh required/);

render(feed([market], {status: 'partial', errors: ['Market fetch failed; cached observation retained.']}));
assert.match(element('kalshiStatus').innerHTML, /Market fetch failed/);
assert.match(element('kalshiStatus').innerHTML, /partial/i);
assert.match(cards(), /Sample player/);

const malicious = '<img src=x onerror=alert(1)>';
render(feed([{...market, label: malicious, title: malicious, ticker: malicious,
  source_url: 'javascript:alert(1)', rules: malicious,
  assessment: {...market.assessment, blockers: [malicious], fee_note: malicious}}],
  {errors: [malicious], unlinked_picks: [{id: malicious, label: malicious, reason: malicious}]}));
const allMarkup = cards() + element('kalshiStatus').innerHTML + element('kalshiUnlinked').innerHTML;
assert.doesNotMatch(allMarkup, /<img|href="javascript:|<script/);
assert.match(allMarkup, /&lt;img/);
assert.doesNotMatch(cards(), /href=/);

for (const source of ['https://external-api.kalshi.com.evil.example/market',
  'http://external-api.kalshi.com/market', 'https://user:pass@docs.kalshi.com/market']) {
  render(feed([{...market, source_url: source}]));
  assert.doesNotMatch(cards(), /href=/);
}
for (const source of ['https://external-api.kalshi.com/trade-api/v2/markets/TEST-MARKET',
  'https://docs.kalshi.com/api-reference/market/get-market']) {
  render(feed([{...market, source_url: source}]));
  assert.match(cards(), /href="https:\/\//);
  assert.match(cards(), /rel="noopener noreferrer"/);
}

render(feed([], {unlinked_picks: [{id: 'p2', label: 'Unlinked pick', reason: 'Exact contract unconfirmed'}]}));
assert.match(cards(), /No Kalshi contracts linked/i);
assert.match(element('kalshiUnlinked').innerHTML, /Unlinked pick/);
assert.match(element('kalshiUnlinked').innerHTML, /Exact contract unconfirmed/);
assert.match(element('kalshiStatus').innerHTML, /Share a Kalshi market ticker/i);
assert.match(element('kalshiStatus').innerHTML, /event.*period.*player.*threshold.*rules/i);
assert.doesNotMatch(cards(), /Sample player|LIVE/);
render(null);
assert.match(element('kalshiStatus').innerHTML, /unavailable/i);
assert.doesNotMatch(cards(), /Sample player/);

const html = fs.readFileSync('index.html', 'utf8');
assert.match(html, /data-view="kalshi"/);
assert.match(html, /id="kalshi"/);
for (const id of ['kalshiStatus', 'kalshiMarkets', 'kalshiUnlinked']) assert.match(html, new RegExp(`id="${id}"`));
assert(html.indexOf('src="kalshi_ui.js"') < html.indexOf('src="app.js"'));
console.log('PASS: Kalshi snapshots, scenarios, stale and missing data, escaped content, official links, empty state, navigation');
