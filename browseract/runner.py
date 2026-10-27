import time
import math
import re

from browseract.errors import BrowserActError, BrowserActTaskError


def validate_timeout(value) -> int:
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value > 0 and value == int(value)
    except (OverflowError, ValueError):
        valid = False
    if not valid:
        raise BrowserActError("Wait Timeout must be a finite positive integer in seconds.")
    return int(value)


def run_bot(
    client, source: str, target_id: str, inputs: dict, timeout=600,
    *, clock=None, wait=None,
) -> dict:
    wait = wait or time.sleep
    clock = clock or time.monotonic
    timeout = validate_timeout(timeout)
    try:
        created = client.create_run(source, target_id, inputs)
    except BrowserActError as error:
        raise BrowserActError(
            f"Task creation could not be confirmed: {error}. Check BrowserAct before resubmitting.",
            status_code=error.status_code, code=error.code,
        ) from None
    value = created.get("task_id") if isinstance(created, dict) else None
    if type(value) not in (str, int) or not re.fullmatch(r"[1-9][0-9]*", str(value)):
        raise BrowserActError("Task creation did not return a valid task_id. Check BrowserAct before resubmitting.")
    task_id = str(value)
    deadline = clock() + timeout

    def fail(message, *, state=None, status_code=None, code=None):
        if state not in ("failed", "canceled"):
            message += (
                ". Waiting has ended. The plugin sent no cancellation request; "
                "the server may cancel the task after its heartbeat expires"
            )
        return BrowserActTaskError(
            client.redact(message), task_id=task_id,
            remote_status=client.redact(state) if isinstance(state, str) else None,
            status_code=status_code,
            code=client.redact(code) if isinstance(code, str) else code,
        )

    def remaining():
        budget = deadline - clock()
        if budget <= 0:
            raise fail("The plugin wait timed out")
        return budget

    def task_state(payload, observed=None):
        if (
            not isinstance(payload, dict)
            or str(payload.get("task_id")) != task_id
            or not isinstance(payload.get("status"), str)
        ):
            prefix = f"Observed task status {observed}; " if observed else ""
            raise fail(prefix + "BrowserAct returned an invalid task response or a mismatched ID", state=observed)
        return payload["status"]

    try:
        while True:
            status = client.get_task_status(task_id, timeout=remaining())
            remaining()
            state = task_state(status)
            if state == "finished":
                detail = client.get_task(task_id, timeout=remaining())
                remaining()
                detail_state = task_state(detail, observed=state)
                if detail_state != "finished":
                    raise fail(f"The task detail does not indicate successful completion: {detail_state}", state=detail_state)
                return detail
            if state in ("pausing", "paused"):
                raise fail(f"Task status is {state}; the plugin did not resume the task", state=state)
            if state in ("failed", "canceled"):
                try:
                    detail = client.get_task(task_id, timeout=remaining())
                    remaining()
                    task_state(detail, observed=state)
                except BrowserActTaskError:
                    raise
                except BrowserActError as error:
                    remaining()
                    raise fail(
                        f"Task status is {state}; reading failure details failed: {error}",
                        state=state, status_code=error.status_code, code=error.code,
                    ) from None
                info = detail.get("task_failure_info")
                code, message = None, f"The task did not complete successfully: {state}"
                if isinstance(info, dict):
                    if type(info.get("code")) in (str, int):
                        code = info["code"]
                        message += f"; code={code}"
                    if isinstance(info.get("message"), str):
                        message += "; " + info["message"]
                raise fail(message, state=state, code=code)
            if state not in ("created", "running"):
                raise fail(f"Unknown task status: {state}", state=state)
            wait(min(3, remaining()))
    except BrowserActTaskError:
        raise
    except BrowserActError as error:
        remaining()
        raise fail(
            f"Task query failed: {error}", status_code=error.status_code, code=error.code,
        ) from None
