"""Public Kalshi transport and provenance tests; all responses are local fixtures."""
import io
import json
import unittest
from http.client import IncompleteRead
from unittest.mock import patch
from urllib.error import HTTPError, URLError

try:
    import kalshi_api
except ModuleNotFoundError:
    kalshi_api = None


BASE = "https://external-api.kalshi.com/trade-api/v2"
TICKER = "KXNBAGAME-26NOV13LALMIL-LAL"
EVENT = "KXNBAGAME-26NOV13LALMIL"
SERIES = "KXNBAGAME"


class Response:
    def __init__(self, value):
        self.body = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body[:size] if size >= 0 else self.body


def market(**changes):
    return dict({"ticker": TICKER, "event_ticker": EVENT,
                 "yes_bid_dollars": "0.4430", "yes_ask_dollars": "0.4610",
                 "volume_fp": "1234.50", "status": "active"}, **changes)


def event(**changes):
    return {"event": dict({"event_ticker": EVENT, "series_ticker": SERIES,
                           "fee_type_override": None,
                           "fee_multiplier_override": None}, **changes)}


def series(**changes):
    return {"series": dict({"ticker": SERIES, "fee_type": "quadratic",
                            "fee_multiplier": 1}, **changes)}


def http_error(code):
    return HTTPError(BASE, code, "private response must not leak", {},
                     io.BytesIO(b"sensitive upstream response"))


class KalshiApiTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(kalshi_api, "The public Kalshi client is missing")

    def test_public_get_preserves_dollar_and_fractional_fields(self):
        with patch.object(kalshi_api, "_open", return_value=Response({"market": market()})) as transport:
            result = kalshi_api.KalshiClient(timeout=7).get_market(TICKER)
        self.assertEqual(result["yes_bid_dollars"], "0.4430")
        self.assertEqual(result["volume_fp"], "1234.50")
        request = transport.call_args.args[0]
        self.assertEqual(request.full_url, f"{BASE}/markets/{TICKER}")
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.get_header("Authorization"))
        self.assertIsNone(request.get_header("Origin"))
        self.assertEqual(transport.call_args.kwargs["timeout"], 7)

    def test_invalid_tickers_are_rejected_before_network(self):
        with patch.object(kalshi_api, "_open") as transport:
            for invalid in ["", "../secret", "KX?token=secret", "https://evil.example", "KX A", None, True]:
                with self.subTest(invalid=invalid), self.assertRaises(kalshi_api.KalshiError):
                    kalshi_api.KalshiClient().get_market(invalid)
        transport.assert_not_called()

    def test_market_must_match_requested_ticker(self):
        with patch.object(kalshi_api, "_open", return_value=Response({"market": market(ticker="OTHER")})):
            with self.assertRaises(kalshi_api.KalshiError):
                kalshi_api.KalshiClient().get_market(TICKER)

    def test_404_uses_historical_market_then_reports_missing(self):
        with patch.object(kalshi_api, "_open", side_effect=[http_error(404), Response({"market": market()})]) as transport:
            self.assertEqual(kalshi_api.KalshiClient().get_market(TICKER)["ticker"], TICKER)
        self.assertEqual(transport.call_args.args[0].full_url, f"{BASE}/historical/markets/{TICKER}")
        with patch.object(kalshi_api, "_open", side_effect=[http_error(404), http_error(404)]) as transport:
            with self.assertRaises(kalshi_api.KalshiError) as raised:
                kalshi_api.KalshiClient().get_market(TICKER)
        self.assertEqual(transport.call_count, 2)
        self.assertNotIn("sensitive", str(raised.exception))

    def test_orderbook_preserves_current_fixed_point_shape(self):
        book = {"yes_dollars": [["0.4430", "1.25"]], "no_dollars": [["0.5390", "10.00"]]}
        with patch.object(kalshi_api, "_open", return_value=Response({"orderbook_fp": book})):
            self.assertEqual(kalshi_api.KalshiClient().get_orderbook(TICKER), book)

    def test_empty_book_is_valid_but_legacy_and_malformed_books_fail(self):
        with patch.object(kalshi_api, "_open", return_value=Response({"orderbook_fp": {"yes_dollars": [], "no_dollars": []}})):
            self.assertEqual(kalshi_api.KalshiClient().get_orderbook(TICKER)["yes_dollars"], [])
        for raw in [{"orderbook": {"yes": [[50, 5]], "no": []}},
                    {"orderbook_fp": {"yes_dollars": [["NaN", "1.00"]], "no_dollars": []}},
                    {"orderbook_fp": {"yes_dollars": [["0.40", "-1.00"]], "no_dollars": []}}]:
            with self.subTest(raw=raw), patch.object(kalshi_api, "_open", return_value=Response(raw)):
                with self.assertRaises(kalshi_api.KalshiError):
                    kalshi_api.KalshiClient().get_orderbook(TICKER)

    def test_event_override_wins_including_zero_and_is_cached(self):
        for multiplier in [0, 2.5]:
            with self.subTest(multiplier=multiplier), patch.object(kalshi_api, "_open", return_value=Response(event(fee_type_override="quadratic", fee_multiplier_override=multiplier))) as transport:
                client = kalshi_api.KalshiClient()
                first = client.get_fee_schedule(market())
                second = client.get_fee_schedule(market())
            self.assertEqual(first["status"], "estimated")
            self.assertEqual(first["fee_multiplier"], str(multiplier))
            self.assertEqual(second, first)
            self.assertEqual(transport.call_count, 1)
            self.assertIn(f"{BASE}/events/{EVENT}", first["source_urls"])

    def test_series_fallback_and_event_series_cache(self):
        with patch.object(kalshi_api, "_open", side_effect=[Response(event()), Response(series(fee_type="quadratic_with_combo_maker_fees", fee_multiplier="1.500"))]) as transport:
            client = kalshi_api.KalshiClient()
            result = client.get_fee_schedule(market())
            client.get_fee_schedule(market())
        self.assertEqual(result["status"], "estimated")
        self.assertEqual(result["fee_multiplier"], "1.5")
        self.assertIn(f"{BASE}/series/{SERIES}", result["source_urls"])
        self.assertEqual(transport.call_count, 2)

    def test_unknown_and_invalid_fee_schedules_are_unavailable(self):
        for fee_type, multiplier in [("flat", 1), ("new_fee_model", 1), ("quadratic", -1), ("quadratic", "NaN"), ("quadratic", True), ("quadratic", None)]:
            with self.subTest(fee_type=fee_type, multiplier=multiplier), patch.object(kalshi_api, "_open", side_effect=[Response(event()), Response(series(fee_type=fee_type, fee_multiplier=multiplier))]):
                result = kalshi_api.KalshiClient().get_fee_schedule(market())
            self.assertEqual(result["status"], "unavailable")
            self.assertTrue(result["note"])

    def test_unverified_event_or_partial_override_does_not_assume_series(self):
        values = [event(fee_type_override="quadratic", fee_multiplier_override=None),
                  event(event_ticker="OTHER"), event(series_ticker=None)]
        for value in values:
            with self.subTest(value=value), patch.object(kalshi_api, "_open", return_value=Response(value)) as transport:
                result = kalshi_api.KalshiClient().get_fee_schedule(market())
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(transport.call_count, 1)
        with patch.object(kalshi_api, "_open", side_effect=http_error(403)):
            self.assertEqual(kalshi_api.KalshiClient().get_fee_schedule(market())["status"], "unavailable")

    def test_discovery_is_one_bounded_page_with_explicit_filters(self):
        with patch.object(kalshi_api, "_open", return_value=Response({"markets": [market()], "cursor": "there-are-more"})) as transport:
            result = kalshi_api.KalshiClient().list_markets(series_ticker=SERIES, limit=10)
        self.assertEqual(result, [market()])
        self.assertEqual(transport.call_count, 1)
        self.assertIn("series_ticker=KXNBAGAME", transport.call_args.args[0].full_url)
        self.assertIn("limit=10", transport.call_args.args[0].full_url)
        self.assertIn("status=open", transport.call_args.args[0].full_url)
        with patch.object(kalshi_api, "_open") as transport:
            for invalid in [0, -1, 1001, True, "10"]:
                with self.assertRaises(kalshi_api.KalshiError):
                    kalshi_api.KalshiClient().list_markets(limit=invalid)
        transport.assert_not_called()

    def test_429_server_and_network_errors_retry_with_a_bound(self):
        for failure in [http_error(429), http_error(503), URLError("private network details")]:
            with self.subTest(failure=failure), patch.object(kalshi_api, "_open", side_effect=[failure, Response({"market": market()})]) as transport, patch.object(kalshi_api.time, "sleep") as pause:
                self.assertEqual(kalshi_api.KalshiClient(retries=1).get_market(TICKER)["ticker"], TICKER)
            self.assertEqual(transport.call_count, 2)
            self.assertEqual(pause.call_count, 1)
        with patch.object(kalshi_api, "_open", side_effect=http_error(429)) as transport, patch.object(kalshi_api.time, "sleep"):
            with self.assertRaises(kalshi_api.KalshiError):
                kalshi_api.KalshiClient(retries=2).get_market(TICKER)
        self.assertEqual(transport.call_count, 3)

    def test_permanent_errors_and_bad_json_do_not_retry(self):
        with patch.object(kalshi_api, "_open", side_effect=http_error(403)) as transport:
            with self.assertRaises(kalshi_api.KalshiError):
                kalshi_api.KalshiClient().get_market(TICKER)
        self.assertEqual(transport.call_count, 1)
        bad = Response({})
        bad.body = b"not json"
        with patch.object(kalshi_api, "_open", return_value=bad) as transport:
            with self.assertRaises(kalshi_api.KalshiError):
                kalshi_api.KalshiClient().get_market(TICKER)
        self.assertEqual(transport.call_count, 1)

    def test_redirects_are_refused(self):
        request = kalshi_api.Request(f"{BASE}/markets/{TICKER}", method="GET")
        redirect = kalshi_api._NoRedirect()
        self.assertIsNone(redirect.redirect_request(request, None, 302, "Found", {}, "https://elsewhere.example"))

    def test_truncated_transport_response_retries_then_raises_sanitized_error(self):
        with patch.object(kalshi_api, "_open", side_effect=IncompleteRead(b"private partial body")) as transport, patch.object(kalshi_api.time, "sleep"):
            with self.assertRaises(kalshi_api.KalshiError) as raised:
                kalshi_api.KalshiClient(retries=1).get_market(TICKER)
        self.assertEqual(transport.call_count, 2)
        self.assertNotIn("private", str(raised.exception))

    def test_bad_transport_settings_and_oversized_json_are_bounded(self):
        for settings in [{"timeout": 0}, {"timeout": float("inf")}, {"timeout": True},
                         {"retries": -1}, {"retries": 6}, {"retries": True}]:
            with self.subTest(settings=settings), self.assertRaises(kalshi_api.KalshiError):
                kalshi_api.KalshiClient(**settings)
        too_large = Response({})
        too_large.body = b" " * (kalshi_api.MAX_RESPONSE_BYTES + 1)
        with patch.object(kalshi_api, "_open", return_value=too_large) as transport:
            with self.assertRaises(kalshi_api.KalshiError):
                kalshi_api.KalshiClient().get_market(TICKER)
        self.assertEqual(transport.call_count, 1)


if __name__ == "__main__":
    unittest.main()
