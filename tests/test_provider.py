import asyncio
from dataclasses import replace
import json
import httpx
import pytest
from rfp_intelligence.providers.llm import LLM, ProviderError
from rfp_intelligence.schemas import Answer


class Trace:
    def event(self, *args):
        pass


def test_invalid_json_is_repaired(config, monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        content = "broken" if len(calls) == 1 else json.dumps({"answer": "Not found in documents"})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    client_type = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs))
    llm = LLM(replace(config, llm_url="http://example.test/v1", llm_model="test"))
    result = asyncio.run(llm.generate("test", "test", {}, Answer, Trace()))
    assert result.answer == "Not found in documents"
    assert len(calls) == 2


def test_timeout_retry_is_bounded(config, monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout", request=request)
    client_type = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs))
    async def no_sleep(seconds):
        pass
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    llm = LLM(replace(config, llm_url="http://example.test/v1", llm_model="test"))
    with pytest.raises(ProviderError):
        asyncio.run(llm.generate("test", "test", {}, Answer, Trace()))
    assert len(calls) == 3
