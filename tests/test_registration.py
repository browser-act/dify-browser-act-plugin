from pathlib import Path

import pytest
from dify_plugin import DifyPluginEnv, Tool, ToolProvider
from dify_plugin.core.plugin_registration import PluginRegistration


def test_sdk_loads_browseract_provider_and_both_tools():
    assert Path("manifest.yaml").is_file(), "The SDK plugin manifest is missing"
    registration = PluginRegistration(DifyPluginEnv())

    provider = registration.get_tool_provider_cls("browseract")
    assert provider is not None and issubclass(provider, ToolProvider)
    tools = registration.tools_configuration[0].tools
    assert {tool.identity.name for tool in tools} == {
        "run_my_bot",
        "run_official_template",
    }
    for tool in tools:
        implementation = registration.get_tool_cls("browseract", tool.identity.name)
        assert implementation is not None and issubclass(implementation, Tool)
    assert registration.configuration.meta.runner.version == "3.12"
    assert any(asset.filename == "icon.svg" for asset in registration.files)


@pytest.mark.parametrize(
    ("tool_name", "target"),
    [("run_my_bot", "bot_id"), ("run_official_template", "template_id")],
)
def test_registered_inputs_default_to_run_without_proxy_region(
    tool_name, target
):
    registration = PluginRegistration(DifyPluginEnv())
    tool = next(
        tool
        for tool in registration.tools_configuration[0].tools
        if tool.identity.name == tool_name
    )
    parameters = {parameter.name: parameter for parameter in tool.parameters}

    assert parameters["operation"].default == "run"
    assert parameters["operation"].form.value == "llm"
    visible_inputs = [p.name for p in tool.parameters if p.form.value == "llm"]
    assert visible_inputs[0] == "operation"
    assert visible_inputs.index("operation") < visible_inputs.index(target)
    assert [option.value for option in parameters["operation"].options] == ["run", "view"]
    labels = {option.value: option.label.en_us for option in parameters["operation"].options}
    expected_run_label = "Run Template" if tool_name == "run_official_template" else "Run Bot"
    assert labels["run"] == expected_run_label
    assert labels["view"] == "View Parameters"
    assert parameters[target].type == "dynamic-select"
    # Workflow passes the provider/tool context only to input-variable controls.
    # A form-section dynamic select stays empty without calling the SDK hook.
    assert parameters[target].form.value == "llm"
    assert parameters[target].required
    assert parameters[target].default is None
    assert parameters["timeout"].default == 600
    assert not parameters["timeout"].required
    assert parameters["input_json"].default == "{}"
    assert not parameters["input_json"].required
    assert parameters["input_json"].form.value == "llm"
    if tool_name == "run_official_template":
        assert "proxy_region" not in parameters
        assert "bot_id" not in parameters
    else:
        assert "proxy_region" not in parameters
        assert "template_id" not in parameters
