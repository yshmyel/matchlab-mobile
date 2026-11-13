/* Public Kalshi research snapshots. This view never submits orders or fetches APIs. */
(function (root) {
  'use strict';

  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
  const list = value => Array.isArray(value) ? value : [];
  const number = value => {
    if (value === null || value === undefined || typeof value === 'boolean' ||
        (typeof value === 'string' && !value.trim())) return null;
    if (!['number', 'string'].includes(typeof value)) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const money = value => {
    const amount = number(value);
    if (amount === null) return 'Unavailable';
    return (amount < 0 ? '-$' : '$') + Math.abs(amount).toLocaleString('en-US', {
      minimumFractionDigits: 2, maximumFractionDigits: 4
    });
  };
  const time = value => {
    const stamp = typeof value === 'string' ? Date.parse(value) : NaN;
    if (!Number.isFinite(stamp)) return 'Time unavailable';
    return new Intl.DateTimeFormat('en-US', {timeZone: 'America/Los_Angeles',
      year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric',
      minute: '2-digit', second: '2-digit'}).format(stamp) + ' PT';
  };
  const source = value => {
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.username || url.password || url.port ||
          !['external-api.kalshi.com', 'docs.kalshi.com'].includes(url.hostname)) return '';
      return `<a class="link" href="${escape(url.href)}" target="_blank" rel="noopener noreferrer">Kalshi source ↗</a>`;
    } catch (_) { return ''; }
  };
  const metric = (label, value) => `<div><dt>${label}</dt><dd>${escape(money(value))}</dd></div>`;

  function marketCard(row, now) {
    if (!row || typeof row !== 'object') return '';
    const quote = row.quote || {}, history = row.history || {}, assessment = row.assessment || {};
    const observed = typeof row.observed_utc === 'string' ? Date.parse(row.observed_utc) : NaN;
    const stale = !Number.isFinite(observed) || now - observed > 120000 || observed > now + 5000;
    const samples = number(history.samples);
    const scenarios = list(assessment.scenarios).filter(item => item && typeof item === 'object');
    const blockers = list(assessment.blockers);
    const expected = number(assessment.expected_profit);
    return `<article class="game kalshi-card">
      <div class="top"><span class="badge${stale ? ' pending' : ''}">${stale ? 'Snapshot / refresh required' : 'Research snapshot'}</span><span>${escape(row.market_status || 'Market status unavailable')}</span></div>
      <h3 class="pick-title">${escape(row.label || row.title || 'Linked market')}</h3>
      ${row.title && row.title !== row.label ? `<p class="foot">${escape(row.title)}</p>` : ''}
      <p class="pick-market">${escape(row.ticker || 'Ticker unavailable')} · ${escape(String(row.side || 'Side unconfirmed').toUpperCase())}</p>
      <p class="foot">Observed ${escape(time(row.observed_utc))}. Quotes are snapshots and may have changed.</p>
      <dl class="kalshi-metrics kalshi-quotes">${metric('Current bid', quote.bid)}${metric('Current ask', quote.ask)}${metric('Spread', quote.spread)}</dl>
      <p class="foot">Buy-side estimates use the ask; exit estimates use the bid. Available size and a future fill are not guaranteed.</p>
      <p class="notice">${stale ? 'Entry assessment paused until a fresh quote is available. ' : ''}${escape(stale ? 'Historical snapshot for research only.' : assessment.status || 'Assessment unavailable')}</p>
      ${blockers.length ? `<ul class="foot">${blockers.map(item => `<li>${escape(item)}</li>`).join('')}</ul>` : ''}
      <h3>Sampled history</h3>
      <p class="foot">${escape(samples === null ? 'Unknown sample count' : samples + ' samples')} · sampled since tracking began ${escape(time(history.first_observed_utc))}. These observations do not establish a future price peak.</p>
      <dl class="kalshi-metrics">${metric('Highest sampled bid', history.high_bid)}${metric('Lowest sampled ask', history.low_ask)}</dl>
      <h3>Research scenario</h3>
      <p class="foot">${escape(number(assessment.contracts) === null ? 'Contract count unavailable' : number(assessment.contracts) + ' contracts')} · ${escape(assessment.edge_status || 'No verified probability edge')}</p>
      <dl class="kalshi-metrics">${metric('Entry cost before fees', assessment.entry_cost)}${metric('Estimated entry fee', assessment.entry_fee_estimate)}${metric('Total entry cost', assessment.total_cost)}${metric('Maximum loss', assessment.max_loss)}${metric('Immediate-exit estimate', assessment.immediate_exit_profit)}${metric('Mathematical winning settlement ceiling', assessment.winning_profit_ceiling)}${metric('Estimated break-even exit price', assessment.breakeven_exit)}${metric('Hypothetical expected profit', expected)}</dl>
      <p class="foot">The winning settlement ceiling is a mathematical payoff limit, conditional on a winning outcome; it is not a price target or a forecast. A losing contract can lose the full entry cost, including fees.</p>
      <h3>Hypothetical exit scenarios</h3>
      ${scenarios.length ? `<div class="table-wrap"><table><thead><tr><th>Exit bid</th><th>Estimated net profit</th><th>Return on entry cost</th></tr></thead><tbody>${scenarios.map(item => `<tr><td>${escape(money(item.exit_price))}</td><td>${escape(money(item.net_profit))}</td><td>${escape(number(item.roi_pct) === null ? 'Unavailable' : number(item.roi_pct).toFixed(2) + '%')}</td></tr>`).join('')}</tbody></table></div>` : '<p class="foot">Scenarios unavailable until a usable entry quote and fee estimate exist.</p>'}
      <p class="foot">Hypothetical prices are assumptions, not predictions that the market will reach them. ${escape(assessment.fee_note || 'Applicable fees must be verified. Estimates can change with fees, order size and fills.')}</p>
      ${row.rules ? `<details><summary>Contract rules</summary><p class="foot">${escape(row.rules)}</p></details>` : ''}
      ${source(row.source_url)}
    </article>`;
  }

  function renderKalshi(feed, now = Date.now()) {
    if (typeof document === 'undefined') return;
    const status = document.getElementById('kalshiStatus');
    const markets = document.getElementById('kalshiMarkets');
    const unlinked = document.getElementById('kalshiUnlinked');
    if (!status || !markets || !unlinked) return;
    const usable = feed && feed.schema_version === 1 && Array.isArray(feed.markets);
    const rows = usable ? feed.markets : [];
    const errors = usable ? list(feed.errors) : [];
    const unmatched = usable ? list(feed.unlinked_picks) : [];
    status.innerHTML = `<p><strong>${usable ? (feed.status === 'partial' || errors.length ? 'Partial update / verify snapshots' : 'Published research snapshots') : 'Kalshi tracking feed unavailable'}</strong>${usable ? ' · Updated ' + escape(time(feed.generated_utc)) : ''}</p>
      ${errors.length ? `<ul>${errors.map(error => `<li>${escape(typeof error === 'string' ? error : JSON.stringify(error))}</li>`).join('')}</ul>` : ''}
      <p>The future maximum price is unknown. Sampled highs and hypothetical profit scenarios are not peak forecasts or guaranteed returns.</p>
      <p>Share a Kalshi market ticker to link a pick. Confirm the exact event, period, player, threshold and settlement rules before comparing it with MatchLab research. Tracking is research only.</p>`;
    markets.innerHTML = rows.length ? rows.map(row => marketCard(row, now)).join('') :
      '<div class="panel empty">No Kalshi contracts linked. Picks are not yet linked to exact contracts; no market prices or price history are available.</div>';
    unlinked.innerHTML = unmatched.length ? `<h3>Picks awaiting an exact market link</h3><ul class="foot">${unmatched.map(row => `<li><strong>${escape(row && (row.label || row.id || row.pick_id) || 'Unlinked pick')}</strong>${row && row.reason ? ' · ' + escape(row.reason) : ''}</li>`).join('')}</ul>` : '';
  }

  root.renderKalshi = renderKalshi;
  if (typeof module !== 'undefined' && module.exports) module.exports = {renderKalshi};
})(typeof globalThis !== 'undefined' ? globalThis : this);
