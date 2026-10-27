from copy import deepcopy
import json

from jsonschema import Draft202012Validator, validators
from jsonschema.exceptions import SchemaError
from referencing import Registry
from referencing.exceptions import Unresolvable

from browseract.errors import BrowserActError


def input_schema(detail: dict) -> dict:
    schema = detail.get("input_schema")
    if not isinstance(schema, dict):
        raise BrowserActError("No input Schema was provided; parameter configuration cannot be generated.")
    root_type = schema.get("type", "object")
    if root_type != "object" and not (isinstance(root_type, list) and "object" in root_type):
        raise BrowserActError("The input Schema must define an object.")
    validator = _validator_class(schema)
    if validator is None:
        raise BrowserActError("The input Schema version is not supported.")
    try:
        validator.check_schema(schema)
    except SchemaError:
        raise BrowserActError("BrowserAct returned an invalid input Schema.") from None
    return schema


def _validator_class(schema: dict):
    return validators.validator_for(
        schema, default=None if "$schema" in schema else Draft202012Validator
    )


def default_inputs(schema: dict) -> dict:
    return {
        name: deepcopy(definition["default"])
        for name, definition in schema.get("properties", {}).items()
        if isinstance(definition, dict) and "default" in definition
    }


def merge_objects(defaults: dict, overrides: dict) -> dict:
    merged = deepcopy(defaults)
    for name, value in overrides.items():
        if isinstance(merged.get(name), dict) and isinstance(value, dict):
            merged[name] = merge_objects(merged[name], value)
        else:
            merged[name] = deepcopy(value)
    return merged


def prepare_inputs(schema: dict, raw) -> dict:
    schema = input_schema({"input_schema": schema})
    overrides = parse_config(raw)
    merged = merge_objects(default_inputs(schema), overrides)
    try:
        error = next(_validator_class(schema)(schema, registry=Registry()).iter_errors(merged), None)
    except Unresolvable:
        raise BrowserActError("The input Schema contains an unresolved or unsupported external reference.") from None
    if error is not None:
        path = list(error.absolute_path)
        if error.validator == "required":
            missing = next((name for name in error.validator_value if name not in error.instance), None)
            if missing is not None:
                path.append(missing)
        pointer = "input" + "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in path)
        raise BrowserActError(f"{pointer} does not match the input Schema ({error.validator}).")
    return merged


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


def parse_config(raw) -> dict:
    if raw is None:
        raw = {}
    try:
        if isinstance(raw, str):
            raw = json.loads(raw.strip() or "{}", parse_constant=_reject_constant)
        json.dumps(raw, allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        raise BrowserActError("Custom parameters must be valid JSON.") from None
    if not isinstance(raw, dict):
        raise BrowserActError("Custom Parameters JSON must be an object.")
    if set(raw) == {"text", "json", "files"}:
        if (
            not isinstance(raw["text"], str)
            or not isinstance(raw["files"], list)
            or not isinstance(raw["json"], list)
            or len(raw["json"]) != 1
            or not isinstance(raw["json"][0], dict)
        ):
            raise BrowserActError("The full Dify JSON output must contain a text string, a files array, and exactly one configuration object in the json array.")
        raw = raw["json"][0]
    return raw
