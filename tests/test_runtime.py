from main import BrowserActPluginEnv


def test_default_sdk_request_budget_leaves_room_for_600_second_wait(monkeypatch):
    monkeypatch.delenv("MAX_REQUEST_TIMEOUT", raising=False)
    assert BrowserActPluginEnv(_env_file=None).MAX_REQUEST_TIMEOUT == 900


def test_sdk_request_budget_can_be_configured_without_changing_source(monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_TIMEOUT", "1200")
    assert BrowserActPluginEnv(_env_file=None).MAX_REQUEST_TIMEOUT == 1200
