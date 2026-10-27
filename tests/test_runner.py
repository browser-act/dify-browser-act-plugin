import math
import pytest

from browseract.client import BrowserActClient
from browseract.errors import BrowserActError
from browseract.runner import run_bot


class Clock:
    def __init__(self):
        self.now = 0
        self.waits = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        assert seconds > 0
        self.waits.append(seconds)
        self.now += seconds


def test_pending_states_are_polled_internally_until_complete(http_api):
    reply, calls = http_api
    reply({"task_id": "10", "status": "created"})
    for state in ("created", "running", "finished"):
        reply({"task_id": "10", "status": state})
    detail = {"task_id": "10", "status": "finished", "output": {"value": 1}, "keep": None}
    reply(detail)
    clock = Clock()

    result = run_bot(BrowserActClient("unit-test-key"), "bot", "1", {}, 600,
                     clock=clock.monotonic, wait=clock.sleep)

    assert result == detail
    assert clock.waits == [3, 3]
    assert [call["method"] for call in calls].count("POST") == 1
    assert all(call["timeout"] <= 30 for call in calls)


@pytest.mark.parametrize("timeout", [5, 600])
def test_deadline_stops_polling_keeps_task_id_and_never_cancels(http_api, timeout):
    reply, calls = http_api
    reply({"task_id": "10", "status": "created"})
    for _ in range(math.ceil(timeout / 3) + 1):
        reply({"task_id": "10", "status": "running"})
    clock = Clock()

    with pytest.raises(BrowserActError, match="[Tt]ime(?:d )?out") as caught:
        if timeout == 600:
            run_bot(BrowserActClient("unit-test-key"), "bot", "1", {},
                    clock=clock.monotonic, wait=clock.sleep)
        else:
            run_bot(BrowserActClient("unit-test-key"), "bot", "1", {}, timeout,
                    clock=clock.monotonic, wait=clock.sleep)

    assert caught.value.task_id == "10"
    assert clock.now == timeout
    assert "server may cancel" in str(caught.value)
    assert "no cancellation request" in str(caught.value)
    assert sum(call["method"] == "POST" for call in calls) == 1
    assert all("/cancel" not in call["url"] and "/resume" not in call["url"] for call in calls)
    if timeout == 5:
        assert clock.waits == [3, 2]
        assert [call["timeout"] for call in calls[1:]] == [5, 2]


@pytest.mark.parametrize("created", [
    {}, [], {"task_id": None}, {"task_id": True}, {"task_id": 1.5}, {"task_id": "../other"},
])
def test_unusable_create_response_is_not_retried_or_polled(http_api, created):
    reply, calls = http_api
    reply(created)
    with pytest.raises(BrowserActError, match="Task creation") as caught:
        run_bot(BrowserActClient("unit-test-key"), "bot", "1", {})
    assert "before resubmitting" in str(caught.value)
    assert len(calls) == 1 and calls[0]["method"] == "POST"


@pytest.mark.parametrize(("payload", "status"), [
    (TimeoutError("unit-test-key"), 200),
    (b"not json", 200),
    ({"code": 100, "msg": "unit-test-key"}, 500),
])
def test_create_error_preserves_uncertainty_and_never_retries(http_api, payload, status):
    reply, calls = http_api
    reply(payload, status)
    with pytest.raises(BrowserActError, match="Task creation") as caught:
        run_bot(BrowserActClient("unit-test-key"), "bot", "1", {})
    assert "before resubmitting" in str(caught.value)
    assert "unit-test-key" not in str(caught.value)
    assert len(calls) == 1


@pytest.mark.parametrize("state", ["pausing", "paused", "unknown_state"])
def test_pause_or_unknown_status_stops_immediately_with_actual_status(http_api, state):
    reply, calls = http_api
    reply({"task_id": "10"})
    reply({"task_id": "10", "status": state})
    clock = Clock()
    with pytest.raises(BrowserActError) as caught:
        run_bot(BrowserActClient("unit-test-key"), "bot", "1", {},
                clock=clock.monotonic, wait=clock.sleep)
    assert caught.value.task_id == "10"
    assert caught.value.remote_status == state
    assert state in str(caught.value)
    assert len(calls) == 2 and clock.waits == []


@pytest.mark.parametrize("state", ["failed", "canceled"])
@pytest.mark.parametrize("info", [None, {"code": 0, "message": "reason unit-test-key"}])
def test_unsuccessful_task_uses_available_failure_detail_without_fabricating_reason(
    http_api, state, info
):
    reply, calls = http_api
    reply({"task_id": "10"})
    reply({"task_id": "10", "status": state})
    detail = {"task_id": "10", "status": state}
    if info is not None:
        detail["task_failure_info"] = info
    reply(detail)
    with pytest.raises(BrowserActError) as caught:
        run_bot(BrowserActClient("unit-test-key"), "bot", "1", {})
    assert caught.value.task_id == "10" and caught.value.remote_status == state
    assert len(calls) == 3
    assert "unit-test-key" not in str(caught.value)
    if info is not None:
        assert caught.value.code == 0
        assert "reason" in str(caught.value)
    else:
        assert caught.value.code is None


@pytest.mark.parametrize("stage", ["status", "detail"])
def test_query_failures_keep_task_id_without_creating_another_task(http_api, stage):
    reply, calls = http_api
    reply({"task_id": "10"})
    if stage == "detail":
        reply({"task_id": "10", "status": "finished"})
    reply({"code": 10112, "msg": "not found"}, 400)
    with pytest.raises(BrowserActError) as caught:
        run_bot(BrowserActClient("unit-test-key"), "bot", "1", {})
    assert caught.value.task_id == "10"
    assert caught.value.status_code == 400 and caught.value.code == 10112
    assert "10112" in str(caught.value)
    assert "server may cancel" in str(caught.value)
    assert sum(call["method"] == "POST" for call in calls) == 1


@pytest.mark.parametrize("stage", ["status", "detail"])
@pytest.mark.parametrize("payload", [[], {"task_id": "other", "status": "finished"},
                                    {"task_id": "10", "status": None}])
def test_malformed_task_response_never_becomes_success(http_api, stage, payload):
    reply, calls = http_api
    reply({"task_id": "10"})
    if stage == "detail":
        reply({"task_id": "10", "status": "finished"})
    reply(payload)
    with pytest.raises(BrowserActError) as caught:
        run_bot(BrowserActClient("unit-test-key"), "bot", "1", {})
    assert caught.value.task_id == "10"
    assert sum(call["method"] == "POST" for call in calls) == 1


def delayed(clock, seconds, payload):
    def response():
        clock.now += seconds
        return payload
    return response


@pytest.mark.parametrize("stage", ["status", "detail"])
def test_late_response_is_not_accepted_as_success(http_api, stage):
    reply, _ = http_api
    clock = Clock()
    reply({"task_id": "10"})
    if stage == "detail":
        reply({"task_id": "10", "status": "finished"})
    reply(delayed(clock, 6, {"task_id": "10", "status": "finished"}))
    with pytest.raises(BrowserActError, match="[Tt]ime(?:d )?out") as caught:
        run_bot(BrowserActClient("unit-test-key"), "bot", "1", {}, 5,
                clock=clock.monotonic, wait=clock.sleep)
    assert caught.value.task_id == "10"


def test_wait_budget_starts_after_post_returns_task_id(http_api):
    reply, _ = http_api
    clock = Clock()
    reply(delayed(clock, 30, {"task_id": "10"}))
    reply(delayed(clock, 4, {"task_id": "10", "status": "finished"}))
    reply({"task_id": "10", "status": "finished", "output": 1})
    actual = run_bot(BrowserActClient("unit-test-key"), "bot", "1", {}, 5,
                     clock=clock.monotonic, wait=clock.sleep)
    assert actual["output"] == 1 and clock.now == 34


def test_failure_detail_request_error_keeps_observed_failure_state(http_api):
    reply, _ = http_api
    reply({"task_id": "10"})
    reply({"task_id": "10", "status": "failed"})
    reply({"code": 123, "msg": "unavailable"}, 500)
    with pytest.raises(BrowserActError) as caught:
        run_bot(BrowserActClient("unit-test-key"), "bot", "1", {})
    assert caught.value.task_id == "10" and caught.value.remote_status == "failed"
    assert caught.value.status_code == 500


def test_bad_failure_detail_cannot_erase_observed_failed_state(http_api):
    reply, _ = http_api
    reply({"task_id": "10"})
    reply({"task_id": "10", "status": "failed"})
    reply({"task_id": "wrong", "status": "finished"})
    with pytest.raises(BrowserActError) as caught:
        run_bot(BrowserActClient("unit-test-key"), "bot", "1", {})
    assert caught.value.task_id == "10" and caught.value.remote_status == "failed"
    assert "failed" in str(caught.value)


@pytest.mark.parametrize("extra_code", [123, {"future": True}])
def test_complete_task_detail_preserves_extra_code_and_message_fields(http_api, extra_code):
    reply, _ = http_api
    reply({"task_id": "10"})
    reply({"task_id": "10", "status": "finished"})
    detail = {"task_id": "10", "status": "finished", "output": None,
              "code": extra_code, "message": "task metadata"}
    reply(detail)
    assert run_bot(BrowserActClient("unit-test-key"), "bot", "1", {}) == detail
