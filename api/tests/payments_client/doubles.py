"""Shared test doubles: fake clock/sleep and a recorded mock transport."""
import json

import httpx

import contract_a


class FakeClock:
    """Injectable clock: starts at 0 and only moves when the test advances it."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeSleep:
    """Injectable sleep: records the requested waits and advances the clock."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.calls = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        self.clock.advance(seconds)


class Recorder:
    """Records every request the client sends through the mock transport."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def transport(self, responder):
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return responder(request)

        return httpx.MockTransport(handler)

    @property
    def count(self) -> int:
        return len(self.requests)

    def body(self, index: int = 0) -> dict:
        return json.loads(self.requests[index].content)

    def header(self, index: int, name: str) -> str | None:
        return self.requests[index].headers.get(name)

    def respond_contract(self, path: str, method: str, status: int, body):
        """A response that is validated against the contract before being returned."""
        contract_a.validate_response(path, method, status, body)
        if body is None:
            return httpx.Response(status)
        return httpx.Response(status, json=body)

    def respond_raw(self, status: int, text: str, content_type: str):
        return httpx.Response(status, text=text, headers={"content-type": content_type})


def make_client(recorder: Recorder, responder, *, clock=None, sleep=None, **overrides):
    """Builds a PaymentsClient over the mock transport with injectable time.

    Asset code, scale and base URL come from the environment unless overridden,
    so the config tests can exercise the env path.
    """
    import payments_client

    kwargs = {
        "http": httpx.Client(transport=recorder.transport(responder)),
        "clock": clock or FakeClock(),
        "sleep": sleep or FakeSleep(clock or FakeClock()),
    }
    kwargs.update(overrides)
    return payments_client.PaymentsClient(**kwargs)