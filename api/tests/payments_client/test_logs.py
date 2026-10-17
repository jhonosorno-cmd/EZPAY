"""Log tests (brief f): no secrets, no ids beyond operation/status/code/requestId."""
import unittest

import doubles

BASE = "http://node.test/v1"
ASSETS = {"node_base_url": BASE, "asset_code": "COP", "asset_scale": 2}
KEY = "0b6c1b2e-8a44-4d19-9c3e-5b7a0d21f8ac"
CONTINUE_200 = {
    "grantId": "g_abc",
    "status": "ACTIVE",
    "limit": {"debitAmount": {"value": "20000000", "assetCode": "COP", "assetScale": 2}},
    "remaining": {"value": "20000000", "assetCode": "COP", "assetScale": 2},
}
SECRET_REF = "interact-ref-7f3a9c"
SECRET_HASH = "hash-b64-xyz-9182"
PAYMENT_201 = {
    "paymentId": "p_789full",
    "status": "PROCESSING",
    "debitAmount": {"value": "2015000", "assetCode": "COP", "assetScale": 2},
    "sentAmount": {"value": "0", "assetCode": "COP", "assetScale": 2},
}
QUOTE_201 = {
    "quoteId": "q_123",
    "debitAmount": PAYMENT_201["debitAmount"],
    "receiveAmount": {"value": "2000000", "assetCode": "COP", "assetScale": 2},
    "expiresAt": "2026-10-16T15:04:05Z",
    "exceedsRemaining": False,
}


def error(status: int, code: str):
    return {"error": {"code": code, "message": code}}


class LogsTest(unittest.TestCase):
    def setUp(self):
        self.recorder = doubles.Recorder()
        self.client = doubles.make_client(self.recorder, self.responder, **ASSETS)

    def responder(self, request):
        path = request.url.path
        if path == "/v1/grants/g_abc/continue":
            return self.recorder.respond_contract(path, "post", 200, CONTINUE_200)
        if path == "/v1/payments/p_789full":
            return self.recorder.respond_contract(
                path, "get", 200,
                {"paymentId": "p_789full", "status": "COMPLETED", "sentAmount": PAYMENT_201["debitAmount"]},
            )
        if path == "/v1/payments":
            return self.recorder.respond_contract(path, "post", 201, PAYMENT_201)
        if path == "/v1/quotes":
            return self.recorder.respond_contract(path, "post", 400, error(400, "INVALID_RECEIVER"))
        raise AssertionError(f"unexpected path {path}")

    def test_flow_logs_without_secrets_or_ids(self):
        with self.assertLogs("payments_client", level="INFO") as captured:
            self.client.continue_grant("g_abc", SECRET_REF, SECRET_HASH, request_id="req-c")
            self.client.get_payment("p_789full", request_id="req-p")
            self.client.create_payment("q_123", KEY, request_id="req-y")
            try:
                self.client.create_quote("g_abc", "https://wallet.test/laura", "2000000", request_id="req-q")
            except Exception:
                pass
        joined = "\n".join(record.getMessage() for record in captured.records)
        for secret in (SECRET_REF, SECRET_HASH, "p_789full", KEY):
            self.assertNotIn(secret, joined, f"a log line leaked {secret}")
        self.assertIn("op=continue_grant", joined)
        self.assertIn("status=200", joined)
        self.assertIn("requestId=req-c", joined)

    def test_error_logs_carry_operation_status_and_code(self):
        with self.assertLogs("payments_client", level="INFO") as captured:
            try:
                self.client.create_quote("g_abc", "https://wallet.test/laura", "2000000", request_id="req-err")
            except Exception:
                pass
        line = captured.records[0].getMessage()
        self.assertIn("op=create_quote", line)
        self.assertIn("status=400", line)
        self.assertIn("code=INVALID_RECEIVER", line)
        self.assertIn("requestId=req-err", line)
        self.assertNotIn("laura", line, "request data does not appear in the logs")


if __name__ == "__main__":
    unittest.main()