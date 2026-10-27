from copy import deepcopy

import pytest
from dify_plugin import DifyPluginEnv
from dify_plugin.core.plugin_registration import PluginRegistration
from jsonschema import Draft202012Validator

from browseract.parameters import parse_config
from tools import run_my_bot, run_official_template


RUN_FIELDS = {
    "task_id", "log_detail_url", "bot_id", "bot_type", "bot_name", "status",
    "created_at", "finished_at", "input", "task_failure_info", "output",
    "output_files", "download_files", "files_expires_at", "steps", "live_url_info", "credit",
}


@pytest.mark.parametrize("tool_name", ["run_my_bot", "run_official_template"])
def test_registered_run_outputs_expose_make_fields_and_file_children(tool_name):
    registration = PluginRegistration(DifyPluginEnv())
    tool = next(t for t in registration.tools_configuration[0].tools if t.identity.name == tool_name)
    schema = tool.output_schema
    assert isinstance(schema, dict), "Named run outputs have not been declared"
    Draft202012Validator.check_schema(schema)
    properties = schema["properties"]
    assert set(properties) == RUN_FIELDS
    for name in ("task_id", "bot_id"):
        assert properties[name]["type"] == "string"
    for fmt in ("csv", "json", "markdown", "md", "xml"):
        file_properties = properties["output_files"]["properties"][fmt]["properties"]
        assert set(file_properties) == {"file_name", "file_size", "download_url"}
    for name in ("download_files", "steps"):
        assert properties[name]["type"] == "array"
        assert properties[name]["items"]["type"] == "object"
    # Bot output has no universal record shape or type.
    for output in ([{"rating": 5}], {"nested": 0}, "text", 0, False, None):
        Draft202012Validator(properties["output"]).validate(output)


@pytest.mark.parametrize("module,tool_class,target", [
    (run_my_bot, run_my_bot.RunMyBotTool, "bot_id"),
    (run_official_template, run_official_template.RunOfficialTemplateTool, "template_id"),
])
@pytest.mark.parametrize("output", [[{"rating": 5}], {"nested": 0}, "text", [], "", 0, False, None])
def test_run_adds_named_fields_without_changing_full_detail(
    monkeypatch, module, tool_class, target, output
):
    detail = {
        "task_id": 9007199254740993, "bot_id": 9007199254740995, "status": "finished",
        "bot_type": "workflow", "bot_name": "Maps", "created_at": "2026-10-20T00:00:00Z",
        "finished_at": "2026-10-20T00:00:01Z", "input": {"limit": 1}, "output": output,
        "output_files": {
            "csv": {"file_name": "data.csv", "file_size": 10, "download_url": "https://example.invalid/csv"},
            "markdown": {"file_name": "data.md", "download_url": "https://example.invalid/md"},
        },
        "download_files": [], "files_expires_at": 1792480000000,
        "task_failure_info": None, "steps": [], "live_url_info": None,
        "log_detail_url": "https://example.invalid/log", "credit": 0,
        "future_field": {"preserve": [False, None]},
    }
    before = deepcopy(detail)
    monkeypatch.setattr(module, "invoke_bot", lambda *_: detail)
    messages = list(tool_class.from_credentials({"api_key": "unit-test-key"}).invoke({
        target: "1", "operation": "run",
    }))
    json_messages = [m for m in messages if m.type.value == "json"]
    assert len(json_messages) == 1
    assert json_messages[0].message.json_object == before
    variables = {
        m.message.variable_name: m.message.variable_value
        for m in messages if m.type.value == "variable"
    }
    assert set(variables) == RUN_FIELDS
    assert len(messages) == 1 + len(RUN_FIELDS)
    assert variables["task_id"] == "9007199254740993"
    assert variables["bot_id"] == "9007199254740995"
    assert variables["output"] == output and type(variables["output"]) is type(output)
    assert variables["output_files"] == detail["output_files"]
    assert variables["download_files"] == [] and variables["credit"] == 0
    assert detail == before


@pytest.mark.parametrize("module,tool_class,target", [
    (run_my_bot, run_my_bot.RunMyBotTool, "bot_id"),
    (run_official_template, run_official_template.RunOfficialTemplateTool, "template_id"),
])
def test_view_still_only_returns_copyable_configuration(monkeypatch, module, tool_class, target):
    config = {"task_id": "business input", "status": "business value", "empty": "", "flag": False}
    monkeypatch.setattr(module, "invoke_bot", lambda *_: config)
    for settings in ({"operation": "view"},):
        messages = list(tool_class.from_credentials({"api_key": "unit-test-key"}).invoke({
            target: "1", **settings,
        }))
        assert len(messages) == 1 and messages[0].type.value == "json"
        assert messages[0].message.json_object == config
        full_copy = {"text": "", "json": [messages[0].message.json_object], "files": []}
        assert parse_config(full_copy) == config


@pytest.mark.parametrize("module,tool_class,target", [
    (run_my_bot, run_my_bot.RunMyBotTool, "bot_id"),
    (run_official_template, run_official_template.RunOfficialTemplateTool, "template_id"),
])
def test_missing_optional_fields_are_not_invented(monkeypatch, module, tool_class, target):
    detail = {"task_id": "10", "status": "finished", "future_field": "raw only"}
    monkeypatch.setattr(module, "invoke_bot", lambda *_: detail)
    messages = list(tool_class.from_credentials({"api_key": "unit-test-key"}).invoke({
        target: "1", "operation": "run",
    }))
    variables = {m.message.variable_name: m.message.variable_value for m in messages if m.type.value == "variable"}
    assert variables == {"task_id": "10", "status": "finished"}
    assert messages[0].message.json_object == detail
