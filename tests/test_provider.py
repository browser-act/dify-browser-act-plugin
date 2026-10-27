import pytest
from urllib.error import URLError
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from provider.browseract import BrowserActProvider


def test_valid_key_is_checked_with_one_read_only_request_even_with_no_bots(http_api):
    reply, calls = http_api
    reply({"items": [], "page": 1, "limit": 1, "total_count": 0, "total_pages": 0})

    assert BrowserActProvider().validate_credentials({"api_key": "unit-test-key"}) is None

    assert calls == [{
        "url": "https://api.browseract.com/v3/bots?page=1&limit=1",
        "method": "GET",
        "authorization": "Bearer unit-test-key",
        "channel": "difyak",
        "body": None,
        "timeout": 30,
    }]


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_failed_auth_check_reports_http_and_api_code_without_exposing_key(
    http_api, caplog, capsys, status
):
    reply, calls = http_api
    reply({"code": 10001, "msg": "Rejected unit-test-key"}, status)

    with pytest.raises(ToolProviderCredentialValidationError) as caught:
        BrowserActProvider().validate_credentials({"api_key": "unit-test-key"})

    assert f"HTTP {status}" in str(caught.value)
    assert "10001" in str(caught.value)
    assert "unit-test-key" not in str(caught.value) + caplog.text + str(capsys.readouterr())
    assert len(calls) == 1


def test_redirect_is_not_followed_and_key_is_not_sent_to_a_different_host(http_api):
    reply, calls = http_api
    reply({}, 302, {"Location": "https://elsewhere.invalid/collect"})

    with pytest.raises(ToolProviderCredentialValidationError, match="HTTP 302"):
        BrowserActProvider().validate_credentials({"api_key": "unit-test-key"})

    assert len(calls) == 1
    assert calls[0]["url"].startswith("https://api.browseract.com/")


def test_json_escaped_key_in_api_error_is_redacted_after_decoding(http_api):
    reply, _ = http_api
    reply(b'{"code":10001,"msg":"Rejected unit-test-\\u006bey"}', 401)

    with pytest.raises(ToolProviderCredentialValidationError) as caught:
        BrowserActProvider().validate_credentials({"api_key": "unit-test-key"})

    assert "unit-test-key" not in str(caught.value)
    assert "[REDACTED]" in str(caught.value)


def test_malformed_structured_error_code_is_not_reflected_back_to_dify(http_api):
    reply, _ = http_api
    reply(b'{"code":{"invalid":"unit-test-\\u006bey"},"msg":"bad response"}', 401)

    with pytest.raises(ToolProviderCredentialValidationError) as caught:
        BrowserActProvider().validate_credentials({"api_key": "unit-test-key"})

    assert "unit-test-key" not in str(caught.value)


@pytest.mark.parametrize(
    ("payload", "status", "message"),
    [
        (b"<html>unit-test-key</html>", 200, "JSON"),
        (b"<html>unit-test-key</html>", 401, "HTTP 401"),
        (b"<html>unit-test-key</html>", 500, "HTTP 500"),
        ({"code": 10020, "msg": "Rejected unit-test-key"}, 200, "10020"),
        ({}, 200, "Bot list"),
        ([], 200, "Bot list"),
    ],
)
def test_malformed_or_business_error_response_never_authenticates(
    http_api, payload, status, message
):
    reply, _ = http_api
    reply(payload, status)

    with pytest.raises(ToolProviderCredentialValidationError, match=message) as caught:
        BrowserActProvider().validate_credentials({"api_key": "unit-test-key"})

    assert "unit-test-key" not in str(caught.value)


@pytest.mark.parametrize("key", [None, "", "   ", 123, "a\nb", "a b", "密钥"])
def test_missing_or_invalid_key_is_rejected_before_any_http_request(http_api, key):
    _, calls = http_api

    with pytest.raises(ToolProviderCredentialValidationError, match="API Key"):
        BrowserActProvider().validate_credentials({"api_key": key})

    assert calls == []


@pytest.mark.parametrize(
    "error", [TimeoutError("unit-test-key"), URLError("unit-test-key")]
)
def test_transport_failure_is_reported_without_key_or_automatic_retry(http_api, error):
    reply, calls = http_api
    reply(error)

    with pytest.raises(ToolProviderCredentialValidationError, match="request failed or timed out") as caught:
        BrowserActProvider().validate_credentials({"api_key": "unit-test-key"})

    assert "unit-test-key" not in str(caught.value)
    assert len(calls) == 1
