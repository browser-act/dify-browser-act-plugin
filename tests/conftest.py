import dify_plugin  # Apply SDK gevent patching before importing HTTP modules.

import json
from collections import deque
from email.message import Message
from io import BytesIO
from urllib.request import HTTPSHandler
from urllib.response import addinfourl

import pytest

from browseract.option_cache import option_cache


@pytest.fixture(autouse=True)
def isolated_option_cache():
    option_cache._entries.clear()
    yield
    option_cache._entries.clear()


@pytest.fixture
def http_api(monkeypatch):
    """Replace only the HTTPS wire boundary; retain urllib's redirect/error handling."""
    responses = deque()
    calls = []

    def reply(payload, status=200, headers=None):
        body = (
            payload
            if isinstance(payload, (bytes, Exception)) or callable(payload)
            else json.dumps(payload).encode()
        )
        responses.append((status, body, headers or {}))

    def https_open(handler, request):
        assert responses, "Unexpected API request"
        calls.append({
            "url": request.full_url,
            "method": request.get_method(),
            "authorization": request.get_header("Authorization"),
            "channel": request.get_header("Api-channel-ak"),
            "body": request.data,
            "timeout": request.timeout,
        })
        status, body, headers = responses.popleft()
        if callable(body):
            body = body()
            if not isinstance(body, (bytes, Exception)):
                body = json.dumps(body).encode()
        if isinstance(body, Exception):
            raise body
        message = Message()
        for name, value in headers.items():
            message[name] = value
        response = addinfourl(BytesIO(body), message, request.full_url, status)
        response.msg = "Test API response"
        return response

    monkeypatch.setattr(HTTPSHandler, "https_open", https_open)
    return reply, calls
