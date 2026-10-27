import pytest
from browseract.errors import BrowserActError

from tools.run_my_bot import RunMyBotTool
from tools.run_official_template import RunOfficialTemplateTool


@pytest.mark.parametrize(
    ("tool", "target", "path"),
    [
        (RunMyBotTool, "bot_id", "/v3/bots/1"),
        (RunOfficialTemplateTool, "template_id", "/v3/bots/templates/1"),
    ],
)
def test_view_returns_only_one_native_json_message_and_ignores_run_settings(
    http_api, tool, target, path
):
    reply, calls = http_api
    reply({
        target: "1", "description": "Do not output", "input_schema": {
            "type": "object", "properties": {
                "URL": {"type": "string", "default": "https://example.com", "description": "hidden"},
                "zero": {"default": 0}, "flag": {"default": False},
                "empty": {"default": ""}, "null": {"default": None},
                "missing": {"type": "string"},
            },
            "required": ["missing"],
        },
    })

    messages = list(tool.from_credentials({"api_key": "unit-test-key"}).invoke({
        target: "1", "operation": "view", "input_json": "invalid", "timeout": -1, "proxy_region": None,
    }))

    assert len(messages) == 1
    assert messages[0].type.value == "json"
    assert messages[0].message.json_object == {
        "URL": "https://example.com", "zero": 0, "flag": False, "empty": "", "null": None,
    }
    assert [(call["method"], call["url"]) for call in calls] == [
        ("GET", "https://api.browseract.com" + path)
    ]


@pytest.mark.parametrize("schema", [
    None, [], {"type": "array"}, {"type": "object", "properties": []},
    {"type": "object", "required": "field"},
    {"$schema": "https://invalid.example/schema", "type": "object"},
])
def test_view_rejects_missing_or_invalid_input_schema(http_api, schema):
    reply, _ = http_api
    reply({"bot_id": "1", "input_schema": schema})

    with pytest.raises(BrowserActError, match="Schema"):
        list(RunMyBotTool.from_credentials({"api_key": "unit-test-key"}).invoke({"bot_id": "1", "operation": "view"}))


@pytest.mark.parametrize("raw", ['{"count":"secret-input"}', '{"text":"","json":[],"files":[]}'])
def test_run_validates_input_before_any_task_request(http_api, raw):
    reply, calls = http_api
    reply({"bot_id": "1", "input_schema": {
        "type": "object", "properties": {"count": {"type": "integer"}}, "required": ["count"],
    }})
    with pytest.raises(BrowserActError):
        list(RunMyBotTool.from_credentials({"api_key": "unit-test-key"}).invoke({
            "bot_id": "1", "operation": "run", "input_json": raw,
        }))
    assert [call["method"] for call in calls] == ["GET"]


def test_invalid_operation_is_rejected_without_api_requests(http_api):
    _, calls = http_api
    with pytest.raises(BrowserActError, match="Operation"):
        list(RunMyBotTool.from_credentials({"api_key": "unit-test-key"}).invoke({
            "bot_id": "1", "operation": "invalid",
        }))
    assert calls == []


def test_valid_schema_without_explicit_defaults_returns_empty_config(http_api):
    reply, _ = http_api
    reply({"bot_id": "1", "input_schema": {"required": ["must_fill"], "properties": {
        "must_fill": {"type": "string"},
        "parent": {"type": "object", "properties": {"child": {"default": 1}}},
    }}})
    messages = list(RunMyBotTool.from_credentials({"api_key": "unit-test-key"}).invoke({"bot_id": "1", "operation": "view"}))
    assert messages[0].message.json_object == {}


@pytest.mark.parametrize("target", [None, 1, "../1", "1?extra=2"])
def test_invalid_target_is_rejected_without_requests(http_api, target):
    _, calls = http_api
    with pytest.raises(BrowserActError, match="ID"):
        list(RunMyBotTool.from_credentials({"api_key": "unit-test-key"}).invoke({"bot_id": target}))
    assert calls == []


def test_mismatched_definition_id_cannot_be_used(http_api):
    reply, calls = http_api
    reply({"bot_id": "2", "input_schema": {}})
    with pytest.raises(BrowserActError, match="ID"):
        list(RunMyBotTool.from_credentials({"api_key": "unit-test-key"}).invoke({"bot_id": "1", "operation": "view"}))
    assert len(calls) == 1


@pytest.mark.parametrize(("tool", "target", "path", "output"), [
    (RunMyBotTool, "bot_id", "/v3/bots/1", {"rows": [{"value": False}]}),
    (RunOfficialTemplateTool, "template_id", "/v3/bots/templates/1", "original\nstring"),
])
def test_run_creates_once_waits_and_returns_complete_task_detail(
    http_api, tool, target, path, output
):
    reply, calls = http_api
    reply({target: "1", "published_at": "2026-10-20" if target == "bot_id" else None,
           "input_schema": {"properties": {
        "filters": {"default": {"country": "US", "limit": 10}},
    }}})
    reply({"task_id": "10", "status": "created"})
    reply({"task_id": "10", "status": "finished"})
    detail = {
        "task_id": 10, "status": "finished", "output": output,
        "output_files": {"json": {"download_url": "https://signed.invalid/result"}},
        "download_files": [{"download_url": "https://signed.invalid/file"}],
        "files_expires_at": 123456, "log_detail_url": "https://example.com/log/10",
        "unknown_future_field": {"keep": [1, False, None]},
    }
    reply(detail)

    messages = list(tool.from_credentials({"api_key": "unit-test-key"}).invoke({
        target: "1", "operation": "run", "proxy_region": "DE",
        "input_json": '{"text":"","json":[{"filters":{"limit":20}}],"files":[]}',
    }))

    json_messages = [message for message in messages if message.type.value == "json"]
    assert len(json_messages) == 1 and messages[0].type.value == "json"
    assert messages[0].message.json_object == detail
    posts = [call for call in calls if call["method"] == "POST"]
    assert len(posts) == 1 and posts[0]["url"] == "https://api.browseract.com" + path + "/runs"
    import json
    expected_body = {"input": {"filters": {"country": "US", "limit": 20}}}
    assert json.loads(posts[0]["body"]) == expected_body
    assert [call["url"] for call in calls[-2:]] == [
        "https://api.browseract.com/v3/bots/runs/10/status",
        "https://api.browseract.com/v3/bots/runs/10",
    ]


@pytest.mark.parametrize("publication", [{}, {"published_at": None}, {"published_at": ""}])
def test_saved_bot_that_is_no_longer_published_never_creates_a_task(http_api, publication):
    reply, calls = http_api
    reply({"bot_id": "1", "input_schema": {"type": "object"}, **publication})
    reply({"task_id": "10", "status": "created"})
    reply({"task_id": "10", "status": "finished"})
    reply({"task_id": "10", "status": "finished"})

    with pytest.raises(BrowserActError, match="not published"):
        list(RunMyBotTool.from_credentials({"api_key": "unit-test-key"}).invoke({
            "operation": "run", "bot_id": "1",
        }))

    assert [(call["method"], call["url"]) for call in calls] == [
        ("GET", "https://api.browseract.com/v3/bots/1")
    ]


@pytest.mark.parametrize("timeout", [0, -1, True, 1.5, "600", None, float("nan"), float("inf"), 10**400])
def test_invalid_wait_timeout_fails_before_post(http_api, timeout):
    reply, calls = http_api
    reply({"bot_id": "1", "input_schema": {}})
    with pytest.raises(BrowserActError, match="[Tt]ime(?:d )?out"):
        list(RunMyBotTool.from_credentials({"api_key": "unit-test-key"}).invoke({
            "operation": "run", "bot_id": "1", "timeout": timeout,
        }))
    assert all(call["method"] == "GET" for call in calls)
