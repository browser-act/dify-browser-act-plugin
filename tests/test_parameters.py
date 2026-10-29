from copy import deepcopy
import json
import pytest

from browseract import parameters
from browseract.errors import BrowserActError


def test_run_does_not_fill_optional_parameters_with_view_placeholders():
    schema = {"type": "object", "properties": {
        "keyword": {"type": "string", "minLength": 1},
        "count": {"type": "integer", "minimum": 1},
        "limit": {"type": "integer", "default": 3},
    }}
    assert parameters.prepare_inputs(schema, "{}") == {"limit": 3}
    schema["required"] = ["keyword"]
    with pytest.raises(BrowserActError, match="input/keyword.*required"):
        parameters.prepare_inputs(schema, "{}")


def test_overrides_merge_objects_replace_arrays_preserve_falsy_values_and_do_not_mutate_defaults():
    schema = {"type": "object", "properties": {
        "filters": {"type": "object", "default": {
            "country": "US", "limit": 10, "tags": ["a"], "nested": {"kept": 1},
        }},
        "zero": {"type": "integer", "default": 1},
        "flag": {"type": "boolean", "default": True},
        "empty": {"type": "string", "default": "value"},
        "nullable": {"type": ["string", "null"], "default": "value"},
    }}
    before = deepcopy(schema)
    raw = json.dumps({
        "filters": {"limit": 20, "tags": ["b"], "nested": {}},
        "zero": 0, "flag": False, "empty": "", "nullable": None,
    })

    actual = parameters.prepare_inputs(schema, raw)

    assert actual == {
        "filters": {"country": "US", "limit": 20, "tags": ["b"], "nested": {"kept": 1}},
        "zero": 0, "flag": False, "empty": "", "nullable": None,
    }
    actual["filters"]["nested"]["kept"] = 2
    assert schema == before


@pytest.mark.parametrize(("raw", "expected"), [
    ('{"text":"","json":[{"value":0}],"files":[]}', {"value": 0}),
    ('{"json":[{"value":1}]}', {"json": [{"value": 1}]}),
    ('{"text":"","json":[{}],"files":[],"other":1}',
     {"text": "", "json": [{}], "files": [], "other": 1}),
    ('{"text":"","json":[{"text":"business","json":[{"x":1}],"files":[]}],"files":[]}',
     {"text": "business", "json": [{"x": 1}], "files": []}),
    ("", {}), (None, {}),
])
def test_config_accepts_direct_object_or_exactly_one_dify_wrapper(raw, expected):
    assert parameters.prepare_inputs({}, raw) == expected


@pytest.mark.parametrize("raw", [
    '{"text":"","json":[],"files":[]}',
    '{"text":"","json":[{},{}],"files":[]}',
    '{"text":"","json":[1],"files":[]}',
    '{"text":1,"json":[{}],"files":[]}',
    '{"text":"","json":[{}],"files":{}}',
    "[]", '"string"', "null", "{", '{"n":NaN}', '{"n":Infinity}',
])
def test_malformed_config_is_a_clear_error_instead_of_silent_defaults(raw):
    with pytest.raises(BrowserActError, match="JSON"):
        parameters.prepare_inputs({}, raw)


@pytest.mark.parametrize(("schema", "raw", "path"), [
    ({"properties": {"count": {"type": "integer"}}}, '{"count":"private-value"}', "input/count"),
    ({"required": ["count"]}, "{}", "input/count"),
    ({"properties": {"filters": {"properties": {"limit": {"maximum": 10}}}}},
     '{"filters":{"limit":20}}', "input/filters/limit"),
    ({"additionalProperties": False}, '{"extra":1}', "input"),
    ({"properties": {"choice": {"oneOf": [{"enum": ["A"]}, {"enum": ["B"]}]}}},
     '{"choice":"C"}', "input/choice"),
    ({"$defs": {"count": {"type": "integer", "minimum": 1}},
      "properties": {"count": {"$ref": "#/$defs/count"}}}, '{"count":0}', "input/count"),
])
def test_final_merged_configuration_is_validated_and_reports_field_path(schema, raw, path):
    with pytest.raises(BrowserActError, match=path) as caught:
        parameters.prepare_inputs(schema, raw)
    assert "private-value" not in str(caught.value)


def test_external_schema_references_are_rejected_without_network_requests(http_api):
    _, calls = http_api
    schema = {"properties": {"x": {"$ref": "https://invalid.example/remote-schema"}}}
    with pytest.raises(BrowserActError, match="reference"):
        parameters.prepare_inputs(schema, '{"x":1}')
    assert calls == []


def test_object_union_schema_accepts_object_config_without_changing_null_fields():
    schema = {"type": ["object", "null"], "properties": {
        "value": {"type": ["string", "null"], "default": "default"},
    }}
    assert parameters.prepare_inputs(schema, '{"value":null}') == {"value": None}


@pytest.mark.parametrize(("raw", "expected"), [
    # Copying the rendered output can replace the indent spaces with NBSP.
    ('{\n\u00a0 "keyword": "elden ring",\n\u00a0 "result_count": 3\n}',
     {"keyword": "elden ring", "result_count": 3}),
    # Some input methods and rich-text pastes use an ideographic space.
    ('{\u3000"keyword"\u3000:\u3000"elden ring"\u3000}', {"keyword": "elden ring"}),
    # Full-width punctuation looks like JSON but is not accepted by json.loads.
    ('｛＂keyword＂：＂elden ring＂，＂result_count＂：3｝',
     {"keyword": "elden ring", "result_count": 3}),
    # A word processor in the path turns the delimiters into curly quotes.
    ('{\u201ckeyword\u201d: \u201celden ring\u201d}', {"keyword": "elden ring"}),
])
def test_pasted_lookalike_characters_are_repaired(raw, expected):
    assert parameters.prepare_inputs({}, raw) == expected


def test_pasted_wrapper_with_invisible_spaces_still_extracts_the_single_configuration():
    raw = ('{\n\u00a0 "files": [],\n\u00a0 "json": [\n\u00a0\u00a0\u00a0 {\n'
           '\u00a0\u00a0\u00a0\u00a0 "keyword": "elden ring"\n\u00a0\u00a0\u00a0 }\n'
           '\u00a0 ],\n\u00a0 "text": ""\n}')
    assert parameters.prepare_inputs({}, raw) == {"keyword": "elden ring"}


def test_repair_leaves_characters_inside_string_values_untouched():
    note = "全角，标点：与＂引号＂和\u00a0空格"
    raw = '{\n\u00a0 "note": "' + note + '"\n}'
    assert parameters.prepare_inputs({}, raw) == {"note": note}


def test_valid_config_still_parses_without_repair():
    assert parameters.prepare_inputs({}, '{"note":"全角，标点"}') == {"note": "全角，标点"}
