"""Interval helpers for grant limits.

The one-off grant of an over-limit payment is requested with a weekly interval
of one repetition (`R1`) that starts at the instant of the request in UTC:
`R` or `Rn` with n > 1 would renew the cap every week, so only `R1` is valid.
"""
from datetime import datetime, timedelta, timezone


def one_off_interval(now: datetime) -> str:
    """Returns `R1/<now in UTC, second precision>/P1W` for the one-off grant.

    `now` must be timezone-aware and UTC; a naive or non-UTC datetime is a
    caller bug and is rejected instead of guessed. The clock is injected: this
    function never reads the wall clock itself.
    """
    if not isinstance(now, datetime):
        raise ValueError("one_off_interval expects a datetime")
    if now.tzinfo is None:
        raise ValueError("one_off_interval expects a timezone-aware datetime in UTC; got a naive datetime")
    if now.utcoffset() != timedelta(0):
        raise ValueError("one_off_interval expects a UTC datetime; convert the instant to UTC first")
    start = now.astimezone(timezone.utc).replace(microsecond=0)
    return f"R1/{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/P1W"