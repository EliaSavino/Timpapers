import unittest
from unittest.mock import patch

import httpx

from timpapers.services.clients import OpenAlexClient


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, responses: list[_FakeResponse], calls: list[dict[str, object]]) -> None:
        self._responses = responses
        self._calls = calls

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        return None

    async def get(self, url: str, params: dict[str, object]) -> _FakeResponse:
        self._calls.append({"url": url, "params": dict(params)})
        return self._responses.pop(0)


class OpenAlexClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_author_works_paginates_until_no_next_cursor(self) -> None:
        responses = [
            _FakeResponse(
                {
                    "meta": {"next_cursor": "cursor-2"},
                    "results": [{"id": "W1"}, {"id": "W2"}],
                }
            ),
            _FakeResponse(
                {
                    "meta": {"next_cursor": None},
                    "results": [{"id": "W3"}],
                }
            ),
        ]
        calls: list[dict[str, object]] = []

        def build_client(*args: object, **kwargs: object) -> _FakeAsyncClient:
            return _FakeAsyncClient(responses, calls)

        with patch.object(httpx, "AsyncClient", side_effect=build_client):
            works = await OpenAlexClient().fetch_author_works("https://openalex.org/A123")

        self.assertEqual(works, [{"id": "W1"}, {"id": "W2"}, {"id": "W3"}])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["params"]["cursor"], "*")
        self.assertEqual(calls[1]["params"]["cursor"], "cursor-2")

