import pytest

from browseract.errors import BrowserActError
from tools.run_my_bot import RunMyBotTool
from tools.run_official_template import RunOfficialTemplateTool


@pytest.mark.parametrize(
    ("tool", "parameter"),
    [(RunMyBotTool, "bot_id"), (RunOfficialTemplateTool, "template_id")],
)
@pytest.mark.parametrize("name", ["A" * 99, "A" * 100, "A" * 101, "模板" * 60])
def test_option_names_only_above_100_characters_are_shortened(http_api, tool, parameter, name):
    reply, _ = http_api
    target_id = "9007199254740993"
    reply({"items": [{parameter: target_id, "name": name, "published_at": "2026-10-23"}],
           "page": 1, "total_pages": 1})

    option = tool.from_credentials({"api_key": "unit-test-key"}).fetch_parameter_options(parameter)[0]

    expected = name if len(name) <= 100 else name[:100] + "…"
    assert option.label.en_us == expected
    assert option.label.zh_hans == expected
    assert option.value == target_id


@pytest.mark.parametrize(
    ("tool", "parameter"),
    [(RunMyBotTool, "bot_id"), (RunOfficialTemplateTool, "template_id")],
)
def test_shortened_name_collisions_do_not_add_ids_to_labels(http_api, tool, parameter):
    reply, _ = http_api
    prefix = "A" * 100
    reply({"items": [
        {parameter: "9007199254740993", "name": prefix + "first", "published_at": "2026-10-23"},
        {parameter: "118154167847668957", "name": prefix + "second", "published_at": "2026-10-23"},
    ], "page": 1, "total_pages": 1})

    options = tool.from_credentials({"api_key": "unit-test-key"}).fetch_parameter_options(parameter)

    assert [option.label.en_us for option in options] == [prefix + "…", prefix + "…"]
    assert [option.value for option in options] == ["9007199254740993", "118154167847668957"]


def test_my_bot_options_load_all_pages_and_only_published_bots_with_exact_ids(http_api):
    reply, calls = http_api
    reply({
        "items": [
            {"bot_id": 9007199254740993, "name": "Same", "published_at": "2026-10-20"},
            {"bot_id": "2", "name": "Draft", "published_at": None},
        ],
        "page": 1,
        "total_pages": 2,
    })
    reply({
        "items": [{"bot_id": "118154167847668957", "name": "Same", "published_at": "2026-10-20"}],
        "page": 2,
        "total_pages": 2,
    })

    options = RunMyBotTool.from_credentials({"api_key": "unit-test-key"}).fetch_parameter_options("bot_id")

    assert [(option.value, option.label.en_us) for option in options] == [
        ("9007199254740993", "Same (9007199254740993)"),
        ("118154167847668957", "Same (118154167847668957)"),
    ]
    assert [call["url"] for call in calls] == [
        "https://api.browseract.com/v3/bots?page=1&limit=100",
        "https://api.browseract.com/v3/bots?page=2&limit=100",
    ]
    assert all(call["method"] == "GET" and call["body"] is None for call in calls)


def test_template_options_use_only_template_pages_and_keep_templates_without_published_at(http_api):
    reply, calls = http_api
    reply({"items": [{"template_id": "3001", "name": "Maps"}], "page": 1, "total_pages": 2})
    reply({"items": [{"template_id": "3002", "name": "Search"}], "page": 2, "total_pages": 2})

    options = RunOfficialTemplateTool.from_credentials({"api_key": "unit-test-key"}).fetch_parameter_options("template_id")

    assert [(option.value, option.label.en_us) for option in options] == [
        ("3001", "Maps"), ("3002", "Search"),
    ]
    assert [call["url"] for call in calls] == [
        "https://api.browseract.com/v3/bots/templates?page=1&limit=500",
        "https://api.browseract.com/v3/bots/templates?page=2&limit=500",
    ]






@pytest.mark.parametrize(
    "page",
    [
        {},
        {"items": {}, "page": 1, "total_pages": 1},
        {"items": [None], "page": 1, "total_pages": 1},
        {"items": [], "page": 1, "total_pages": -1},
        {"items": [], "page": 2, "total_pages": 2},
        {"items": [], "page": 1, "total_pages": True},
        {"items": [], "page": 1},
        {"items": [], "page": 1, "total_pages": "2"},
        {"items": [], "page": 1, "total_pages": 2},
    ],
)
def test_invalid_pagination_does_not_silently_return_an_empty_or_partial_list(http_api, page):
    reply, _ = http_api
    reply(page)

    with pytest.raises(BrowserActError, match="list"):
        RunMyBotTool.from_credentials({"api_key": "unit-test-key"}).fetch_parameter_options("bot_id")


@pytest.mark.parametrize("identifier", [None, True, 9007199254740993.0, ""])
def test_invalid_ids_are_not_coerced_into_selectable_values(http_api, identifier):
    reply, _ = http_api
    reply({"items": [{"template_id": identifier, "name": "Invalid"}], "page": 1, "total_pages": 1})

    with pytest.raises(BrowserActError, match="options"):
        RunOfficialTemplateTool.from_credentials({"api_key": "unit-test-key"}).fetch_parameter_options("template_id")


def test_pagination_change_is_reported_instead_of_returning_an_incomplete_list(http_api):
    reply, _ = http_api
    reply({"items": [{"template_id": "1", "name": "One"}], "page": 1, "total_pages": 2})
    reply({"items": [{"template_id": "2", "name": "Two"}], "page": 2, "total_pages": 1})

    with pytest.raises(BrowserActError, match="list"):
        RunOfficialTemplateTool.from_credentials({"api_key": "unit-test-key"}).fetch_parameter_options("template_id")


def test_duplicate_ids_are_reported_instead_of_creating_ambiguous_choices(http_api):
    reply, _ = http_api
    reply({"items": [
        {"template_id": "3001", "name": "First"},
        {"template_id": "3001", "name": "Second"},
    ], "page": 1, "total_pages": 1})

    with pytest.raises(BrowserActError, match="options"):
        RunOfficialTemplateTool.from_credentials({"api_key": "unit-test-key"}).fetch_parameter_options("template_id")


@pytest.mark.parametrize(
    ("tool", "parameter"),
    [(RunMyBotTool, "bot_id"), (RunOfficialTemplateTool, "template_id")],
)
def test_an_authenticated_empty_list_returns_no_fake_or_default_target(http_api, tool, parameter):
    reply, _ = http_api
    reply({"items": [], "page": 1, "total_pages": 0})

    assert tool.from_credentials({"api_key": "unit-test-key"}).fetch_parameter_options(parameter) == []


@pytest.mark.parametrize(
    ("tool", "parameter"),
    [(RunMyBotTool, "bot_id"), (RunOfficialTemplateTool, "template_id")],
)
def test_option_load_failure_is_not_converted_into_an_empty_list(http_api, tool, parameter):
    reply, _ = http_api
    reply({"code": 10001, "msg": "Rejected unit-test-key"}, 401)

    with pytest.raises(BrowserActError) as caught:
        tool.from_credentials({"api_key": "unit-test-key"}).fetch_parameter_options(parameter)

    assert caught.value.status_code == 401
    assert caught.value.code == 10001
    assert "unit-test-key" not in str(caught.value)


def test_options_are_loaded_fresh_for_each_account(http_api):
    reply, calls = http_api
    reply({"items": [{"bot_id": "1", "name": "Account A", "published_at": "now"}],
           "page": 1, "total_pages": 1})
    reply({"items": [{"bot_id": "2", "name": "Account B", "published_at": "now"}],
           "page": 1, "total_pages": 1})

    first = RunMyBotTool.from_credentials({"api_key": "account-a-key"}).fetch_parameter_options("bot_id")
    second = RunMyBotTool.from_credentials({"api_key": "account-b-key"}).fetch_parameter_options("bot_id")

    assert [(item.value, item.label.en_us) for item in first] == [("1", "Account A")]
    assert [(item.value, item.label.en_us) for item in second] == [("2", "Account B")]
    assert [call["authorization"] for call in calls] == ["Bearer account-a-key", "Bearer account-b-key"]
