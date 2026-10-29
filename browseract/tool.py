from browseract.errors import BrowserActError
from browseract.parameters import default_inputs, input_schema, prepare_inputs
from browseract.runner import run_bot, validate_timeout


def invoke_bot(client, source: str, parameters: dict) -> dict:
    operation = parameters.get("operation", "run")
    if operation not in ("view", "run"):
        raise BrowserActError("Operation must be View Parameters or Run.")
    if source == "bot":
        target_field = "bot_id"
    else:
        target_field = "template_id"
    detail = client.get_definition(source, parameters.get(target_field))
    schema = input_schema(detail)
    if operation == "view":
        return default_inputs(schema)
    inputs = prepare_inputs(schema, parameters.get("input_json", "{}"))
    timeout = validate_timeout(parameters.get("timeout", 600))
    if source == "bot" and not detail.get("published_at"):
        raise BrowserActError("The selected Bot is not published or has been unpublished; no task was created. Refresh the list and select again.")
    return run_bot(client, source, parameters[target_field], inputs, timeout)
