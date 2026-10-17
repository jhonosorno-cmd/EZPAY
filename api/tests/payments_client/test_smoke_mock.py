"""Optional smoke test (brief g): runs against the Prism mock only when it is up."""
import os
import unittest

import httpx


class PrismSmokeTest(unittest.TestCase):
    def test_health_against_prism(self):
        base = os.environ.get("NODE_BASE_URL", "http://localhost:4000/v1").rstrip("/")
        try:
            response = httpx.get(f"{base}/health", timeout=0.5)
        except Exception:
            self.skipTest("Prism mock (npm run mock:a) is not running")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})


if __name__ == "__main__":
    unittest.main()