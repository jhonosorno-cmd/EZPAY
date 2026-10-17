"""Tests for one_off_interval(now): always R1, start is the request instant in UTC."""
from datetime import datetime, timedelta, timezone
import unittest

from payments_client import one_off_interval


class OneOffIntervalTest(unittest.TestCase):
    def test_always_starts_with_r1(self):
        now = datetime(2026, 10, 17, 14, 3, 9, tzinfo=timezone.utc)
        self.assertTrue(one_off_interval(now).startswith("R1/"))

    def test_never_repeats_the_weekly_cap(self):
        now = datetime(2026, 10, 17, 14, 3, 9, tzinfo=timezone.utc)
        result = one_off_interval(now)
        self.assertFalse(result.startswith("R/"))
        self.assertFalse(result.startswith("R2"))
        self.assertFalse(result.startswith("R52"))

    def test_start_is_the_injected_now_truncated_to_seconds(self):
        now = datetime(2026, 10, 17, 14, 3, 9, 999999, tzinfo=timezone.utc)
        self.assertEqual(one_off_interval(now), "R1/2026-10-17T14:03:09Z/P1W")

    def test_microseconds_are_dropped_not_rounded(self):
        now = datetime(2026, 10, 17, 23, 59, 59, 500001, tzinfo=timezone.utc)
        self.assertEqual(one_off_interval(now), "R1/2026-10-17T23:59:59Z/P1W")

    def test_ends_with_p1w(self):
        now = datetime(2026, 10, 17, 14, 3, 9, tzinfo=timezone.utc)
        self.assertTrue(one_off_interval(now).endswith("/P1W"))

    def test_naive_now_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            one_off_interval(datetime(2026, 10, 17, 14, 3, 9))
        self.assertIn("UTC", str(ctx.exception))

    def test_non_utc_timezone_is_rejected(self):
        now = datetime(2026, 10, 17, 9, 3, 9, tzinfo=timezone(timedelta(hours=-5)))
        with self.assertRaises(ValueError) as ctx:
            one_off_interval(now)
        self.assertIn("UTC", str(ctx.exception))

    def test_is_pure(self):
        """The function must not read the wall clock on its own."""
        import inspect

        import payments_client.intervals as intervals

        source = inspect.getsource(intervals)
        self.assertNotIn("now()", source)
        self.assertNotIn("utcnow", source)


if __name__ == "__main__":
    unittest.main()