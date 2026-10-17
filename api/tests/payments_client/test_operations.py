"""Operation tests (brief a): one test per Contract A operation, error codes by `code`,
and transport failures that are never business errors."""
import unittest

import httpx

import doubles
import payments_client
from payments_client import PaymentsError, UpstreamUnavailable

BASE = "http://node.test/v1"
ASSETS = {"node_base_url": BASE, "asset_code": "COP", "asset_scale": 2}

GRANT_201 = {"grantId": "g_abc", "status": "PENDING", "interactUrl": "https://auth.wallet.test/interact/abc"}
CONTINUE_200 = {
    "grantId": "g_abc",
    "status": "ACTIVE",
    "limit": {"debitAmount": {"value": "20000000", "assetCode": "COP", "assetScale": 2}},
    "remaining": {"value": "20000000", "assetCode": "COP", "assetScale": 2},
}
GRANT_200 = {
    "grantId": "g_abc",
    "status": "ACTIVE",
    "limit": {"debitAmount": {"value": "20000000", "assetCode": "COP", "assetScale": 2}},
    "spent": {"value": "2015000", "assetCode": "COP", "assetScale": 2},
    "remaining": {"value": "17985000", "assetCode": "COP", "assetScale": 2},
}
QUOTE_201 = {
    "quoteId": "q_123",
    "debitAmount": {"value": "2015000", "assetCode": "COP", "assetScale": 2},
    "receiveAmount": {"value": "2000000", "assetCode": "COP", "assetScale": 2},
    "expiresAt": "2026-10-16T15:04:05Z",
    "exceedsRemaining": False,
}
PAYMENT_201 = {
    "paymentId": "p_789",
    "status": "COMPLETED",
    "debitAmount": {"value": "2015000", "assetCode": "COP", "assetScale": 2},
    "sentAmount": {"value": "2015000", "assetCode": "COP", "assetScale": 2},
}
PAYMENT_STATE_200 = {"paymentId": "p_789", "status": "COMPLETED", "sentAmount": {"value": "2015000", "assetCode": "COP", "assetScale": 2}}


class OperationsTest(unittest.TestCase):
    def setUp(self):
        self.recorder = doubles.Recorder()
        self.clock = doubles.FakeClock()
        self.sleep = doubles.FakeSleep(self.clock)

    def client(self, responder):
        return doubles.make_client(self.recorder, responder, clock=self.clock, sleep=self.sleep, **ASSETS)

    def test_health(self):
        client = self.client(lambda r: self.recorder.respond_contract("/v1/health", "get", 200, {"ok": True}))
        self.assertEqual(client.health(), {"ok": True})
        request = self.recorder.requests[0]
        self.assertEqual((request.method, request.url.path), ("GET", "/v1/health"))

    def test_create_grant_sends_limit_built_from_config(self):
        client = self.client(lambda r: self.recorder.respond_contract("/v1/grants", "post", 201, GRANT_201))
        result = client.create_grant(
            "demo-user",
            "https://wallet.test/marta",
            "http://frontend.test/grant-callback",
            "2000000",
            interval="R52/2026-10-16T00:00:00Z/P1W",
        )
        self.assertEqual(result, GRANT_201)
        request = self.recorder.requests[0]
        self.assertEqual((request.method, request.url.path), ("POST", "/v1/grants"))
        self.assertEqual(
            self.recorder.body(0),
            {
                "userId": "demo-user",
                "walletAddress": "https://wallet.test/marta",
                "finishUri": "http://frontend.test/grant-callback",
                "limit": {
                    "debitAmount": {"value": "2000000", "assetCode": "COP", "assetScale": 2},
                    "interval": "R52/2026-10-16T00:00:00Z/P1W",
                },
            },
        )

    def test_create_grant_without_interval(self):
        client = self.client(lambda r: self.recorder.respond_contract("/v1/grants", "post", 201, GRANT_201))
        client.create_grant("demo-user", "https://wallet.test/marta", "http://frontend.test/grant-callback", "2000000")
        self.assertEqual(self.recorder.body(0)["limit"], {"debitAmount": {"value": "2000000", "assetCode": "COP", "assetScale": 2}})

    def test_continue_grant_forwards_interact_ref_and_hash_verbatim(self):
        client = self.client(lambda r: self.recorder.respond_contract("/v1/grants/g_abc/continue", "post", 200, CONTINUE_200))
        result = client.continue_grant("g_abc", " interact-ref raw ", " hash raw ")
        self.assertEqual(result, CONTINUE_200)
        request = self.recorder.requests[0]
        self.assertEqual((request.method, request.url.path), ("POST", "/v1/grants/g_abc/continue"))
        self.assertEqual(self.recorder.body(0), {"interactRef": " interact-ref raw ", "hash": " hash raw "})

    def test_get_grant(self):
        client = self.client(lambda r: self.recorder.respond_contract("/v1/grants/g_abc", "get", 200, GRANT_200))
        self.assertEqual(client.get_grant("g_abc"), GRANT_200)
        request = self.recorder.requests[0]
        self.assertEqual((request.method, request.url.path), ("GET", "/v1/grants/g_abc"))

    def test_cancel_grant_sends_delete_and_ignores_body(self):
        client = self.client(lambda r: self.recorder.respond_contract("/v1/grants/g_abc", "delete", 204, None))
        self.assertIsNone(client.cancel_grant("g_abc"))
        request = self.recorder.requests[0]
        self.assertEqual((request.method, request.url.path), ("DELETE", "/v1/grants/g_abc"))

    def test_create_quote(self):
        client = self.client(lambda r: self.recorder.respond_contract("/v1/quotes", "post", 201, QUOTE_201))
        result = client.create_quote("g_abc", "https://wallet.test/laura", "2000000")
        self.assertEqual(result, QUOTE_201)
        request = self.recorder.requests[0]
        self.assertEqual((request.method, request.url.path), ("POST", "/v1/quotes"))
        self.assertEqual(
            self.recorder.body(0),
            {
                "grantId": "g_abc",
                "receiver": "https://wallet.test/laura",
                "receiveAmount": {"value": "2000000", "assetCode": "COP", "assetScale": 2},
            },
        )

    def test_create_payment_sends_idempotency_key(self):
        client = self.client(lambda r: self.recorder.respond_contract("/v1/payments", "post", 201, PAYMENT_201))
        result = client.create_payment("q_123", "0b6c1b2e-8a44-4d19-9c3e-5b7a0d21f8ac")
        self.assertEqual(result, PAYMENT_201)
        request = self.recorder.requests[0]
        self.assertEqual((request.method, request.url.path), ("POST", "/v1/payments"))
        self.assertEqual(self.recorder.header(0, "Idempotency-Key"), "0b6c1b2e-8a44-4d19-9c3e-5b7a0d21f8ac")
        self.assertEqual(self.recorder.body(0), {"quoteId": "q_123"})

    def test_get_payment(self):
        client = self.client(lambda r: self.recorder.respond_contract("/v1/payments/p_789", "get", 200, PAYMENT_STATE_200))
        self.assertEqual(client.get_payment("p_789"), PAYMENT_STATE_200)
        request = self.recorder.requests[0]
        self.assertEqual((request.method, request.url.path), ("GET", "/v1/payments/p_789"))

    def test_request_id_is_propagated(self):
        client = self.client(lambda r: self.recorder.respond_contract("/v1/quotes", "post", 201, QUOTE_201))
        client.create_quote("g_abc", "https://wallet.test/laura", "2000000", request_id="abc-123")
        self.assertEqual(self.recorder.header(0, "X-Request-Id"), "abc-123")

    def test_no_request_id_header_when_not_given(self):
        client = self.client(lambda r: self.recorder.respond_contract("/v1/quotes", "post", 201, QUOTE_201))
        client.create_quote("g_abc", "https://wallet.test/laura", "2000000")
        self.assertIsNone(self.recorder.header(0, "X-Request-Id"))

    def test_amount_value_must_be_digit_string(self):
        client = self.client(lambda r: httpx.Response(201, json=QUOTE_201))
        for bad in ("20.5", "2e3", "", " 20", "20 ", 2000, None):
            with self.assertRaises(ValueError):
                client.create_quote("g_abc", "https://wallet.test/laura", bad)

    def test_business_errors_raise_with_code_and_status(self):
        cases = [
            ("create_grant", "/v1/grants", "post", 400, "INVALID_AMOUNT",
             lambda c: c.create_grant("demo-user", "https://wallet.test/marta", "http://f.test/cb", "2000000")),
            ("create_grant", "/v1/grants", "post", 400, "INVALID_WALLET",
             lambda c: c.create_grant("demo-user", "https://wallet.test/none", "http://f.test/cb", "2000000")),
            ("create_grant", "/v1/grants", "post", 502, "UPSTREAM_ERROR",
             lambda c: c.create_grant("demo-user", "https://wallet.test/marta", "http://f.test/cb", "2000000")),
            ("continue_grant", "/v1/grants/g_abc/continue", "post", 400, "INVALID_HASH",
             lambda c: c.continue_grant("g_abc", "ir", "h")),
            ("continue_grant", "/v1/grants/g_abc/continue", "post", 403, "GRANT_REJECTED",
             lambda c: c.continue_grant("g_abc", "ir", "h")),
            ("continue_grant", "/v1/grants/g_abc/continue", "post", 409, "GRANT_NOT_PENDING",
             lambda c: c.continue_grant("g_abc", "ir", "h")),
            ("get_grant", "/v1/grants/g_abc", "get", 404, "GRANT_NOT_FOUND",
             lambda c: c.get_grant("g_abc")),
            ("cancel_grant", "/v1/grants/g_abc", "delete", 404, "GRANT_NOT_FOUND",
             lambda c: c.cancel_grant("g_abc")),
            ("cancel_grant", "/v1/grants/g_abc", "delete", 502, "UPSTREAM_ERROR",
             lambda c: c.cancel_grant("g_abc")),
            ("create_quote", "/v1/quotes", "post", 400, "INVALID_AMOUNT",
             lambda c: c.create_quote("g_abc", "https://wallet.test/laura", "2000000")),
            ("create_quote", "/v1/quotes", "post", 400, "INVALID_RECEIVER",
             lambda c: c.create_quote("g_abc", "https://wallet.test/laura", "2000000")),
            ("create_quote", "/v1/quotes", "post", 401, "GRANT_INVALID",
             lambda c: c.create_quote("g_abc", "https://wallet.test/laura", "2000000")),
            ("create_quote", "/v1/quotes", "post", 404, "GRANT_NOT_FOUND",
             lambda c: c.create_quote("g_abc", "https://wallet.test/laura", "2000000")),
            ("create_payment", "/v1/payments", "post", 400, "IDEMPOTENCY_KEY_REQUIRED",
             lambda c: c.create_payment("q_123", "0b6c1b2e-8a44-4d19-9c3e-5b7a0d21f8ac")),
            ("create_payment", "/v1/payments", "post", 401, "GRANT_INVALID",
             lambda c: c.create_payment("q_123", "0b6c1b2e-8a44-4d19-9c3e-5b7a0d21f8ac")),
            ("create_payment", "/v1/payments", "post", 403, "LIMIT_EXCEEDED",
             lambda c: c.create_payment("q_123", "0b6c1b2e-8a44-4d19-9c3e-5b7a0d21f8ac")),
            ("create_payment", "/v1/payments", "post", 404, "QUOTE_NOT_FOUND",
             lambda c: c.create_payment("q_123", "0b6c1b2e-8a44-4d19-9c3e-5b7a0d21f8ac")),
            ("create_payment", "/v1/payments", "post", 409, "QUOTE_EXPIRED",
             lambda c: c.create_payment("q_123", "0b6c1b2e-8a44-4d19-9c3e-5b7a0d21f8ac")),
            ("create_payment", "/v1/payments", "post", 422, "IDEMPOTENCY_KEY_REUSED",
             lambda c: c.create_payment("q_123", "0b6c1b2e-8a44-4d19-9c3e-5b7a0d21f8ac")),
            ("get_payment", "/v1/payments/p_789", "get", 404, "PAYMENT_NOT_FOUND",
             lambda c: c.get_payment("p_789")),
        ]
        for name, path, method, status, code, call in cases:
            with self.subTest(operation=name, code=code):
                recorder = doubles.Recorder()
                clock = doubles.FakeClock()
                client = doubles.make_client(
                    recorder,
                    lambda r, path=path, method=method, status=status, code=code:
                        recorder.respond_contract(path, method, status, {"error": {"code": code, "message": code}}),
                    clock=clock,
                    sleep=doubles.FakeSleep(clock),
                    **ASSETS,
                )
                with self.assertRaises(PaymentsError) as ctx:
                    call(client)
                self.assertEqual(ctx.exception.code, code)
                self.assertEqual(ctx.exception.status, status)
                self.assertEqual(recorder.count, 1, "a business error must not be retried")

    def test_transport_error_is_upstream_unavailable(self):
        def responder(r):
            raise httpx.ConnectError("connection refused")

        client = self.client(responder)
        with self.assertRaises(UpstreamUnavailable):
            client.create_quote("g_abc", "https://wallet.test/laura", "2000000")
        self.assertNotIsInstance(UpstreamUnavailable("x"), PaymentsError)

    def test_timeout_is_upstream_unavailable(self):
        def responder(r):
            raise httpx.ReadTimeout("timed out")

        client = self.client(responder)
        with self.assertRaises(UpstreamUnavailable):
            client.get_grant("g_abc")

    def test_non_json_success_body_is_upstream_unavailable(self):
        recorder = self.recorder
        client = self.client(lambda r: recorder.respond_raw(200, "<html>boom</html>", "text/html"))
        with self.assertRaises(UpstreamUnavailable):
            client.get_grant("g_abc")

    def test_error_without_contract_shape_is_upstream_unavailable(self):
        recorder = self.recorder
        client = self.client(lambda r: recorder.respond_raw(502, '{"boom": true}', "application/json"))
        with self.assertRaises(UpstreamUnavailable):
            client.get_grant("g_abc")

    def test_errors_do_not_confuse_types(self):
        self.assertFalse(issubclass(UpstreamUnavailable, PaymentsError))
        self.assertFalse(issubclass(PaymentsError, UpstreamUnavailable))


if __name__ == "__main__":
    unittest.main()