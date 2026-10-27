import pytest

import browseract.option_cache as cache_module
from browseract.errors import BrowserActError
from tools.run_my_bot import RunMyBotTool
from tools.run_official_template import RunOfficialTemplateTool


@pytest.mark.parametrize(
    ("tool", "parameter", "response"),
    [
        (RunMyBotTool, "bot_id", {
            "items": [{"bot_id": "1", "name": "Mine", "published_at": "now"}],
            "page": 1, "total_pages": 1,
        }),
        (RunOfficialTemplateTool, "template_id", {
            "items": [{"template_id": "1", "name": "Template"}],
            "page": 1, "total_pages": 1,
        }),
    ],
)
def test_returning_to_node_reuses_options_across_tool_instances(http_api, tool, parameter, response):
    reply, calls = http_api
    reply(response)
    reply(response)
    first = tool.from_credentials({"api_key": "repeat-key"}).fetch_parameter_options(parameter)
    second = tool.from_credentials({"api_key": "repeat-key"}).fetch_parameter_options(parameter)

    assert first == second
    assert len(calls) == 1


def bot_page(name="Mine", **extra):
    return {"items": [{"bot_id": "1", "name": name, "published_at": "now", **extra}],
            "page": 1, "total_pages": 1}


def test_expiry_is_sixty_seconds_and_hits_do_not_extend_it(http_api, monkeypatch):
    reply, calls = http_api
    clock = [100.0]
    monkeypatch.setattr(cache_module, "monotonic", lambda: clock[0])
    reply(bot_page("Old"))
    reply(bot_page("Renamed"))
    tool = RunMyBotTool.from_credentials({"api_key": "unit-test-key"})
    assert tool.fetch_parameter_options("bot_id")[0].label.en_us == "Old"
    clock[0] = 159.999
    assert tool.fetch_parameter_options("bot_id")[0].label.en_us == "Old"
    clock[0] = 160.0
    assert tool.fetch_parameter_options("bot_id")[0].label.en_us == "Renamed"
    assert len(calls) == 2


def test_failures_after_expiry_never_return_stale_options_or_cache_errors(http_api, monkeypatch):
    reply, calls = http_api
    clock = [0.0]
    monkeypatch.setattr(cache_module, "monotonic", lambda: clock[0])
    reply(bot_page())
    reply({"msg": "Unauthorized"}, 401)
    reply({"msg": "Forbidden"}, 403)
    reply(bot_page("Recovered"))
    tool = RunMyBotTool.from_credentials({"api_key": "unit-test-key"})
    tool.fetch_parameter_options("bot_id")
    clock[0] = 60
    for code in (401, 403):
        with pytest.raises(BrowserActError) as caught:
            tool.fetch_parameter_options("bot_id")
        assert caught.value.status_code == code
    assert tool.fetch_parameter_options("bot_id")[0].label.en_us == "Recovered"
    assert len(calls) == 4




@pytest.mark.parametrize("change", ["api_key", "user_id"])
def test_cached_options_do_not_cross_credentials_or_users(http_api, change):
    reply, calls = http_api
    reply(bot_page("A"))
    reply(bot_page("B"))
    first = RunMyBotTool.from_credentials({"api_key": "key-a"}, user_id="user-a")
    second = RunMyBotTool.from_credentials(
        {"api_key": "key-b" if change == "api_key" else "key-a"},
        user_id="user-b" if change == "user_id" else "user-a",
    )
    assert first.fetch_parameter_options("bot_id")[0].label.en_us == "A"
    assert second.fetch_parameter_options("bot_id")[0].label.en_us == "B"
    assert first.fetch_parameter_options("bot_id")[0].label.en_us == "A"
    assert len(calls) == 2


@pytest.mark.parametrize('items', [
    [{'bot_id': '1', 'name': None, 'published_at': 'now'}],
    [{'bot_id': '1', 'name': 'Duplicate', 'published_at': 'now'}] * 2,
])
def test_invalid_bot_options_are_not_cached(http_api, items):
    reply, calls = http_api
    reply({'items': items, 'page': 1, 'total_pages': 1})
    reply(bot_page('Recovered'))
    tool = RunMyBotTool.from_credentials({'api_key': 'unit-test-key'})
    with pytest.raises(BrowserActError):
        tool.fetch_parameter_options('bot_id')
    assert tool.fetch_parameter_options('bot_id')[0].label.en_us == 'Recovered'
    assert len(calls) == 2


def test_sources_are_separate_with_the_same_credentials(http_api):
    reply, calls = http_api
    reply(bot_page("Personal"))
    reply({"items": [{"template_id": "1", "name": "Official"}], "page": 1, "total_pages": 1})
    mine = RunMyBotTool.from_credentials({"api_key": "unit-test-key"})
    official = RunOfficialTemplateTool.from_credentials({"api_key": "unit-test-key"})
    for _ in range(2):
        assert mine.fetch_parameter_options("bot_id")[0].label.en_us == "Personal"
        assert official.fetch_parameter_options("template_id")[0].label.en_us == "Official"
    assert len(calls) == 2


def test_partial_pagination_failure_does_not_cache_partial_options(http_api):
    reply, calls = http_api
    reply({**bot_page(), "total_pages": 2})
    reply({"msg": "Temporary failure"}, 500)
    reply({**bot_page(), "total_pages": 2})
    reply({"items": [{"bot_id": "2", "name": "Second", "published_at": "now"}],
           "page": 2, "total_pages": 2})
    tool = RunMyBotTool.from_credentials({"api_key": "unit-test-key"})
    with pytest.raises(BrowserActError):
        tool.fetch_parameter_options("bot_id")
    assert [o.value for o in tool.fetch_parameter_options("bot_id")] == ["1", "2"]
    assert [o.value for o in tool.fetch_parameter_options("bot_id")] == ["1", "2"]
    assert len(calls) == 4


def test_mutating_options_does_not_change_later_callers(http_api):
    reply, calls = http_api
    reply(bot_page())
    tool = RunMyBotTool.from_credentials({"api_key": "unit-test-key"})
    first = tool.fetch_parameter_options("bot_id")
    first[0].label.en_us = "Mutated first"
    second = tool.fetch_parameter_options("bot_id")
    assert second[0].label.en_us == "Mine"
    second.clear()
    assert tool.fetch_parameter_options("bot_id")[0].label.en_us == "Mine"
    assert len(calls) == 1


def test_cache_is_bounded_and_evicts_oldest_entry(http_api):
    reply, calls = http_api
    for index in range(129):
        reply(bot_page(str(index)))
        tool = RunMyBotTool.from_credentials({"api_key": f"cache-key-{index}"})
        assert tool.fetch_parameter_options("bot_id")[0].label.en_us == str(index)
    reply(bot_page("Reloaded"))
    assert RunMyBotTool.from_credentials({"api_key": "cache-key-0"}).fetch_parameter_options(
        "bot_id"
    )[0].label.en_us == "Reloaded"
    assert len(calls) == 130


def test_cached_published_bot_still_checks_current_publication_before_run(http_api):
    reply, calls = http_api
    reply(bot_page())
    reply({"bot_id": "1", "published_at": None, "input_schema": {}})
    tool = RunMyBotTool.from_credentials({"api_key": "unit-test-key"})
    tool.fetch_parameter_options("bot_id")
    with pytest.raises(BrowserActError, match="not published"):
        list(tool.invoke({"operation": "run", "bot_id": "1"}))
    assert len(calls) == 2
    assert calls[-1]["url"] == "https://api.browseract.com/v3/bots/1"
    assert all(call["method"] == "GET" for call in calls)




@pytest.mark.parametrize(("cls", "target"), [
    (RunMyBotTool, "bot_id"), (RunOfficialTemplateTool, "template_id"),
])
def test_view_always_reads_current_definition(http_api, cls, target):
    reply, calls = http_api
    tool = cls.from_credentials({"api_key": "unit-test-key"})
    for value in ("Old default", "New default"):
        reply({target: "1", "input_schema": {"properties": {"q": {"default": value}}}})
        messages = list(tool.invoke({target: "1", "operation": "view"}))
        assert messages[0].message.json_object == {"q": value}
        assert len(messages) == 1
    assert len(calls) == 2
