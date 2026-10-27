"""Observe channel attribution at the HTTP boundary through public SDK calls."""
import json

import pytest

from provider.browseract import BrowserActProvider
from tools.run_my_bot import RunMyBotTool
from tools.run_official_template import RunOfficialTemplateTool


@pytest.mark.parametrize(("tool_cls", "target", "path"), [
    (RunMyBotTool, "bot_id", "/v3/bots"),
    (RunOfficialTemplateTool, "template_id", "/v3/bots/templates"),
])
def test_channel_is_consistent_across_auth_options_view_create_and_queries(
    http_api, tool_cls, target, path
):
    reply, calls = http_api
    page = {"items": [], "page": 1, "total_pages": 0}
    reply(page)
    BrowserActProvider().validate_credentials({"api_key": "unit-test-key"})
    reply({"items": [{target: "1", "name": "Sample", "published_at": "now"}],
           "page": 1, "total_pages": 1})
    tool = tool_cls.from_credentials({"api_key": "unit-test-key"})
    assert len(tool.fetch_parameter_options(target)) == 1
    definition = {target: "1", "published_at": "now", "input_schema": {
        "type": "object", "properties": {"query": {"type": "string", "default": "hello"}}
    }}
    reply(definition)
    view = list(tool.invoke({target: "1", "operation": "view"}))
    assert len(view) == 1 and view[0].message.json_object == {"query": "hello"}
    reply(definition)
    reply({"task_id": "10", "status": "created"})
    reply({"task_id": "10", "status": "finished"})
    reply({"task_id": "10", "status": "finished", "output": {"ok": True}})
    result = list(tool.invoke({target: "1", "operation": "run"}))
    assert result[0].message.json_object["status"] == "finished"
    assert len(calls) == 7
    assert all(call["channel"] == "difyak" for call in calls)
    assert all(call["authorization"] == "Bearer unit-test-key" for call in calls)
    assert all(call["url"].startswith("https://api.browseract.com/") for call in calls)
    posts = [call for call in calls if call["method"] == "POST"]
    assert len(posts) == 1
    assert posts[0]["url"].endswith(path + "/1/runs")
    assert json.loads(posts[0]["body"]) == {"input": {"query": "hello"}}
