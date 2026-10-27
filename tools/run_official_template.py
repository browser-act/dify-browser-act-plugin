from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities import ParameterOption

from browseract.client import BrowserActClient
from browseract.option_cache import option_cache
from browseract.options import parameter_options
from browseract.outputs import run_output_variables
from browseract.tool import invoke_bot


class RunOfficialTemplateTool(Tool):
    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        if parameter != "template_id":
            raise ValueError("Unsupported dynamic parameter.")
        client = BrowserActClient(self.runtime.credentials.get("api_key"))
        return option_cache.get(
            self.runtime.credentials["api_key"], self.runtime.user_id,
            "official_template:" + parameter,
            lambda: parameter_options(client.list_templates(), "template_id"),
        )

    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        detail = invoke_bot(BrowserActClient(self.runtime.credentials.get("api_key")), "template", tool_parameters)
        yield self.create_json_message(detail)
        if tool_parameters.get("operation", "run") == "run":
            for name, value in run_output_variables(detail).items():
                yield self.create_variable_message(name, value)
