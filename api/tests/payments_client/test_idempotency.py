"""Idempotency tests (brief c): same key and quoteId on retries, PAYMENT_PENDING on exhaustion."""
import unittest

import payments_client
from payments_client import PaymentPending, PaymentsError

import doubles

BASE = "http://node.test/v1"
ASSETS = {"node_base_url": BASE, "asset_code": "COP", "asset_scale": 2}
KEY = "0b6c1b2e-8a44-4d19-9c3e-5b7a0d21f8ac"
PAYMENT_201 = {
    "paymentId": "p_789",
    "status": "PROCESSING",
    "debitAmount": {"value": "2015000", "assetCode": "COP", "assetScale": 2},
    "sentAmount": {"value": "0", "assetCode": "COP", "assetScale": 2},
}


def error(status: int, code: str):
    return {"error": {"code": code, "message": code}}


class IdempotencyTest(unittest.TestCase):
    def run_client(self, script):
        """script: list of callables(request) -> httpx.Response, consumed per request."""
        recorder = doubles.Recorder()
        clock = doubles.FakeClock()
        sleep = doubles.FakeSleep(clock)
        steps = iter(script)

        def responder(request):
            return next(steps)(request)

        client = doubles.make_client(recorder, responder, clock=clock, sleep=sleep, **ASSETS)
        return client, recorder, sleep

    def test_502_502_201_same_key_and_quote_id(self):
        recorder = doubles.Recorder()
        client = doubles.make_client(
            recorder,
            lambda r: recorder.respond_contract("/v1/payments", "post", 201, PAYMENT_201)
            if recorder.count > 2
            else recorder.respond_contract("/v1/payments", "post", 502, error(502, "UPSTREAM_ERROR")),
            **ASSETS,
        )
        result = client.create_payment("q_123", KEY)
        self.assertEqual(result["paymentId"], "p_789")
        self.assertEqual(recorder.count, 3)
        for index in range(3):
            self.assertEqual(recorder.header(index, "Idempotency-Key"), KEY, "the caller's key is never replaced")
            self.assertEqual(recorder.body(index), {"quoteId": "q_123"})
        self.assertEqual([request.url.path for request in recorder.requests], ["/v1/payments"] * 3)

    def test_retry_waits_are_half_second_then_one_second(self):
        client, recorder, sleep = self.run_client(
            [
                lambda r: doubles.Recorder.respond_contract(recorder, "/v1/payments", "post", 502, error(502, "UPSTREAM_ERROR")),
                lambda r: doubles.Recorder.respond_contract(recorder, "/v1/payments", "post", 201, PAYMENT_201),
            ]
        )
        client.create_payment("q_123", KEY)
        self.assertEqual(sleep.calls, [0.5])

    def test_three_502_exhaustion_returns_pending_never_rejection(self):
        recorder = doubles.Recorder()
        client = doubles.make_client(
            recorder,
            lambda r: recorder.respond_contract("/v1/payments", "post", 502, error(502, "UPSTREAM_ERROR")),
            **ASSETS,
        )
        result = client.create_payment("q_123", KEY)
        self.assertIsInstance(result, PaymentPending)
        self.assertIsNone(result.payment_id)
        self.assertEqual(recorder.count, 3)
        for index in range(3):
            self.assertEqual(recorder.header(index, "Idempotency-Key"), KEY)

    def test_payment_in_progress_retries_with_same_key(self):
        recorder = doubles.Recorder()
        client = doubles.make_client(
            recorder,
            lambda r: recorder.respond_contract("/v1/payments", "post", 201, PAYMENT_201)
            if recorder.count > 1
            else recorder.respond_contract("/v1/payments", "post", 409, error(409, "PAYMENT_IN_PROGRESS")),
            **ASSETS,
        )
        result = client.create_payment("q_123", KEY)
        self.assertEqual(result["paymentId"], "p_789")
        self.assertEqual(recorder.count, 2)
        self.assertEqual(recorder.header(0, "Idempotency-Key"), KEY)
        self.assertEqual(recorder.header(1, "Idempotency-Key"), KEY)
        self.assertEqual(recorder.body(0), {"quoteId": "q_123"})
        self.assertEqual(recorder.body(1), {"quoteId": "q_123"})

    def test_internal_error_is_retried_like_upstream_error(self):
        recorder = doubles.Recorder()
        client = doubles.make_client(
            recorder,
            lambda r: recorder.respond_contract("/v1/payments", "post", 201, PAYMENT_201)
            if recorder.count > 1
            else recorder.respond_contract("/v1/payments", "post", 500, error(500, "INTERNAL_ERROR")),
            **ASSETS,
        )
        result = client.create_payment("q_123", KEY)
        self.assertEqual(result["paymentId"], "p_789")
        self.assertEqual(recorder.count, 2)

    def test_network_failure_exhaustion_returns_pending(self):
        def responder(r):
            raise __import__("httpx").ConnectError("connection refused")

        recorder = doubles.Recorder()
        client = doubles.make_client(recorder, responder, **ASSETS)
        result = client.create_payment("q_123", KEY)
        self.assertIsInstance(result, PaymentPending)
        self.assertEqual(recorder.count, 3)
        self.assertEqual(recorder.header(2, "Idempotency-Key"), KEY)

    def test_business_4xx_is_returned_without_retries(self):
        cases = [
            (409, "QUOTE_EXPIRED"),
            (404, "QUOTE_NOT_FOUND"),
            (403, "LIMIT_EXCEEDED"),
            (401, "GRANT_INVALID"),
            (422, "IDEMPOTENCY_KEY_REUSED"),
        ]
        for status, code in cases:
            with self.subTest(code=code):
                recorder = doubles.Recorder()
                client = doubles.make_client(
                    recorder,
                    lambda r, status=status, code=code:
                        recorder.respond_contract("/v1/payments", "post", status, error(status, code)),
                    **ASSETS,
                )
                with self.assertRaises(PaymentsError) as ctx:
                    client.create_payment("q_123", KEY)
                self.assertEqual(ctx.exception.code, code)
                self.assertEqual(recorder.count, 1)

    def test_retry_budget_of_15_seconds_stops_the_retries(self):
        recorder = doubles.Recorder()
        clock = doubles.FakeClock()

        def slow_sleep(seconds):
            clock.advance(16.0)  # one wait already blows the budget

        client = doubles.make_client(
            recorder,
            lambda r: recorder.respond_contract("/v1/payments", "post", 502, error(502, "UPSTREAM_ERROR")),
            clock=clock,
            sleep=slow_sleep,
            **ASSETS,
        )
        result = client.create_payment("q_123", KEY)
        self.assertIsInstance(result, PaymentPending)
        self.assertEqual(recorder.count, 1)


if __name__ == "__main__":
    unittest.main()