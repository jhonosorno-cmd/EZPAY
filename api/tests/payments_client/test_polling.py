"""Polling tests (brief d): wait_for_payment until COMPLETED/FAILED, PAYMENT_PENDING on timeout."""
import unittest

import payments_client
from payments_client import PaymentPending

import doubles

BASE = "http://node.test/v1"
ASSETS = {"node_base_url": BASE, "asset_code": "COP", "asset_scale": 2}
AMOUNT = {"value": "2015000", "assetCode": "COP", "assetScale": 2}


def state(status: str):
    return {"paymentId": "p_789", "status": status, "sentAmount": AMOUNT}


class PollingTest(unittest.TestCase):
    def test_polls_until_completed(self):
        recorder = doubles.Recorder()
        script = iter([state("PROCESSING"), state("PROCESSING"), state("COMPLETED")])
        client = doubles.make_client(
            recorder,
            lambda r: recorder.respond_contract("/v1/payments/p_789", "get", 200, next(script)),
            **ASSETS,
        )
        result = client.wait_for_payment("p_789")
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(recorder.count, 3)
        for request in recorder.requests:
            self.assertEqual((request.method, request.url.path), ("GET", "/v1/payments/p_789"))

    def test_polling_timeout_returns_pending_with_the_payment_id(self):
        recorder = doubles.Recorder()
        clock = doubles.FakeClock()
        sleep = doubles.FakeSleep(clock)
        client = doubles.make_client(
            recorder,
            lambda r: recorder.respond_contract("/v1/payments/p_789", "get", 200, state("PROCESSING")),
            clock=clock,
            sleep=sleep,
            **ASSETS,
        )
        result = client.wait_for_payment("p_789", interval=2.0, timeout=10.0)
        self.assertIsInstance(result, PaymentPending)
        self.assertEqual(result.payment_id, "p_789")
        self.assertEqual(recorder.count, 6, "interval 2s over a 10s budget")
        self.assertEqual(sleep.calls, [2.0, 2.0, 2.0, 2.0, 2.0])

    def test_failed_is_returned_and_is_not_pending(self):
        recorder = doubles.Recorder()
        client = doubles.make_client(
            recorder,
            lambda r: recorder.respond_contract("/v1/payments/p_789", "get", 200, state("FAILED")),
            **ASSETS,
        )
        result = client.wait_for_payment("p_789")
        self.assertEqual(result["status"], "FAILED")
        self.assertNotIsInstance(result, PaymentPending)
        self.assertEqual(recorder.count, 1)

    def test_no_extra_calls_after_a_final_state(self):
        recorder = doubles.Recorder()
        script = iter([state("PROCESSING"), state("COMPLETED")])
        client = doubles.make_client(
            recorder,
            lambda r: recorder.respond_contract("/v1/payments/p_789", "get", 200, next(script)),
            **ASSETS,
        )
        client.wait_for_payment("p_789")
        self.assertEqual(recorder.count, 2)

    def test_default_interval_and_timeout_are_about_one_and_ten_seconds(self):
        recorder = doubles.Recorder()
        clock = doubles.FakeClock()
        sleep = doubles.FakeSleep(clock)
        client = doubles.make_client(
            recorder,
            lambda r: recorder.respond_contract("/v1/payments/p_789", "get", 200, state("PROCESSING")),
            clock=clock,
            sleep=sleep,
            **ASSETS,
        )
        result = client.wait_for_payment("p_789")
        self.assertIsInstance(result, PaymentPending)
        self.assertEqual(sleep.calls, [1.0] * 10)
        self.assertEqual(recorder.count, 11)

    def test_request_id_is_propagated_on_every_poll(self):
        recorder = doubles.Recorder()
        script = iter([state("PROCESSING"), state("COMPLETED")])
        client = doubles.make_client(
            recorder,
            lambda r: recorder.respond_contract("/v1/payments/p_789", "get", 200, next(script)),
            **ASSETS,
        )
        client.wait_for_payment("p_789", request_id="req-9")
        self.assertEqual(recorder.header(0, "X-Request-Id"), "req-9")
        self.assertEqual(recorder.header(1, "X-Request-Id"), "req-9")


if __name__ == "__main__":
    unittest.main()