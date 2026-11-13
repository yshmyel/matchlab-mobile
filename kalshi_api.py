"""Bounded public Kalshi market-data reads. No credentials or trading operations."""
import json
import math
import random
import re
import time
from decimal import Decimal, InvalidOperation
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
FEE_SCHEDULE_URL = "https://kalshi.com/fee-schedule"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
QUADRATIC_FEES = frozenset({"quadratic", "quadratic_with_maker_fees",
                            "quadratic_with_combo_maker_fees"})
_TICKER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z")


class KalshiError(RuntimeError):
    """A public market lookup failed or supplied unverifiable data."""


class _HTTPStatusError(KalshiError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Kalshi market data returned HTTP {status}.")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open(request, *, timeout):
    # The public-data client cannot follow redirects to another service.
    return build_opener(_NoRedirect()).open(request, timeout=timeout)


def _ticker(value):
    if not isinstance(value, str) or not _TICKER.fullmatch(value):
        raise KalshiError("A valid Kalshi ticker is required.")
    return value


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


class KalshiClient:
    def __init__(self, timeout=10, retries=2):
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or not 0 < timeout <= 60):
            raise KalshiError("Timeout must be greater than zero and at most 60 seconds.")
        if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 5:
            raise KalshiError("Retries must be an integer from zero through five.")
        self.timeout = timeout
        self.retries = retries
        self._events = {}
        self._series = {}

    def _get(self, path, params=None):
        url = BASE_URL + path
        if params:
            url += "?" + urlencode(params)
        request = Request(url, method="GET", headers={
            "Accept": "application/json", "User-Agent": "MatchLabResearch/1.0"})
        for attempt in range(self.retries + 1):
            try:
                with _open(request, timeout=self.timeout) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise KalshiError("Kalshi market-data response exceeded the size limit.")
                try:
                    result = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    raise KalshiError("Kalshi returned invalid market-data JSON.") from None
                if not isinstance(result, dict):
                    raise KalshiError("Kalshi returned an invalid market-data object.")
                return result
            except HTTPError as error:
                status = error.code
                error.close()
                if (status != 429 and not 500 <= status <= 599) or attempt == self.retries:
                    raise _HTTPStatusError(status) from None
            except (URLError, TimeoutError, OSError, HTTPException):
                if attempt == self.retries:
                    raise KalshiError("Kalshi market data could not be reached.") from None
            # 429 does not promise Retry-After; keep both delay and attempts bounded.
            time.sleep(min(0.25 * (2 ** attempt), 2.0) + random.uniform(0, 0.1))
        raise KalshiError("Kalshi market data could not be retrieved.")

    def get_market(self, ticker):
        ticker = _ticker(ticker)
        try:
            result = self._get(f"/markets/{ticker}")
        except _HTTPStatusError as error:
            if error.status != 404:
                raise
            result = self._get(f"/historical/markets/{ticker}")
        market = result.get("market")
        if not isinstance(market, dict) or market.get("ticker") != ticker:
            raise KalshiError("Kalshi did not return the requested market ticker.")
        return market

    def get_orderbook(self, ticker):
        ticker = _ticker(ticker)
        book = self._get(f"/markets/{ticker}/orderbook").get("orderbook_fp")
        if not isinstance(book, dict):
            raise KalshiError("Kalshi did not return a fixed-point order book.")
        for side in ("yes_dollars", "no_dollars"):
            levels = book.get(side)
            if not isinstance(levels, list):
                raise KalshiError("Kalshi returned an invalid order-book side.")
            for level in levels:
                if (not isinstance(level, list) or len(level) != 2
                        or not all(isinstance(value, str) for value in level)):
                    raise KalshiError("Kalshi returned an invalid fixed-point price level.")
                price, quantity = (_decimal(value) for value in level)
                if price is None or quantity is None or not 0 <= price <= 1 or quantity <= 0:
                    raise KalshiError("Kalshi returned an invalid fixed-point price level.")
        return book

    def get_fee_schedule(self, market):
        """Resolve event overrides first. Estimates describe hypothetical taker fees."""
        sources = [FEE_SCHEDULE_URL]
        unavailable = {"status": "unavailable", "fee_type": None,
                       "fee_multiplier": None, "source_urls": sources,
                       "note": "The current fee schedule could not be verified."}
        try:
            event_ticker = _ticker(market.get("event_ticker") if isinstance(market, dict) else None)
            event_url = f"{BASE_URL}/events/{event_ticker}"
            sources.append(event_url)
            if event_ticker not in self._events:
                event = self._get(f"/events/{event_ticker}").get("event")
                if not isinstance(event, dict) or event.get("event_ticker") != event_ticker:
                    raise KalshiError("Kalshi did not return the requested event.")
                self._events[event_ticker] = event
            event = self._events[event_ticker]
            fee_type = event.get("fee_type_override")
            multiplier = event.get("fee_multiplier_override")
            if (fee_type is None) != (multiplier is None):
                unavailable["note"] = "The event fee override is incomplete."
                return unavailable
            if fee_type is None:
                series_ticker = _ticker(event.get("series_ticker"))
                sources.append(f"{BASE_URL}/series/{series_ticker}")
                if series_ticker not in self._series:
                    series = self._get(f"/series/{series_ticker}").get("series")
                    if not isinstance(series, dict) or series.get("ticker") != series_ticker:
                        raise KalshiError("Kalshi did not return the requested series.")
                    self._series[series_ticker] = series
                series = self._series[series_ticker]
                fee_type, multiplier = series.get("fee_type"), series.get("fee_multiplier")
            factor = _decimal(multiplier)
            unavailable["fee_type"] = fee_type if isinstance(fee_type, str) else None
            if factor is not None and factor >= 0:
                unavailable["fee_multiplier"] = str(factor.normalize())
            if not isinstance(fee_type, str) or fee_type not in QUADRATIC_FEES:
                unavailable["note"] = "This fee structure is unsupported; net profit is unavailable."
                return unavailable
            if factor is None or factor < 0:
                unavailable["note"] = "The fee multiplier is missing or invalid."
                return unavailable
            return {"status": "estimated", "fee_type": fee_type,
                    "fee_multiplier": str(factor.normalize()), "source_urls": sources,
                    "note": "Single-fill taker fee estimate. Member rounding, split fills, waivers, and future fee changes may differ."}
        except KalshiError:
            return unavailable

    def list_markets(self, series_ticker=None, event_ticker=None, limit=100):
        """Return one bounded page of open, non-combo discovery candidates."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise KalshiError("Market discovery limit must be an integer from 1 through 1000.")
        params = {"status": "open", "mve_filter": "exclude", "limit": limit}
        if series_ticker is not None:
            params["series_ticker"] = _ticker(series_ticker)
        if event_ticker is not None:
            params["event_ticker"] = _ticker(event_ticker)
        markets = self._get("/markets", params).get("markets")
        if not isinstance(markets, list):
            raise KalshiError("Kalshi did not return a market list.")
        result = markets[:limit]
        for market in result:
            if not isinstance(market, dict):
                raise KalshiError("Kalshi returned an invalid discovery market.")
            _ticker(market.get("ticker"))
        return result
