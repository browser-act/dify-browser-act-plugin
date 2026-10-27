import json
import re
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from browseract.errors import BrowserActError


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class BrowserActClient:
    def __init__(self, api_key: str):
        if not isinstance(api_key, str) or not api_key.strip():
            raise BrowserActError("Configure your BrowserAct API Key.")
        api_key = api_key.strip()
        if any(not 33 <= ord(character) <= 126 for character in api_key):
            raise BrowserActError("The BrowserAct API Key format is invalid.")
        self._api_key = api_key

    def redact(self, message: str) -> str:
        return message.replace(self._api_key, "[REDACTED]")

    def _get(self, path: str, parameters: dict | None = None, *, timeout=30):
        return self._request("GET", path, parameters=parameters, timeout=timeout)

    def _request(self, method: str, path: str, *, parameters=None, body=None, timeout=30):
        url = "https://api.browseract.com" + path
        if parameters:
            url += "?" + urlencode(parameters)
        request = Request(
            url,
            data=json.dumps(body, allow_nan=False).encode() if body is not None else None,
            headers={
                "Authorization": "Bearer " + self._api_key,
                "api-channel-ak": "difyak",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            try:
                with build_opener(_NoRedirect()).open(request, timeout=min(30, timeout)) as response:
                    status, raw = response.status, response.read()
            except HTTPError as error:
                with error:
                    status, raw = error.code, error.read()
        except (URLError, OSError, HTTPException):
            raise BrowserActError("The BrowserAct request failed or timed out. Please try again later.") from None
        raw = raw.replace(self._api_key.encode(), b"[REDACTED]")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            if 200 <= status < 300:
                raise BrowserActError(
                    f"BrowserAct returned a non-JSON response (HTTP {status}).", status_code=status
                ) from None
            data = {}
        is_task_payload = (
            method == "GET" and path.startswith("/v3/bots/runs/")
            and 200 <= status < 300 and isinstance(data, dict)
            and "task_id" in data and "status" in data
        )
        # Task metadata is not an API error envelope; preserve all its fields.
        code = data.get("code") if isinstance(data, dict) and not is_task_payload else None
        if code is not None and type(code) not in (int, str):
            raise BrowserActError(
                f"BrowserAct returned an invalid error response (HTTP {status}).", status_code=status
            ) from None
        if not 200 <= status < 300 or code not in (None, 0, "0"):
            reason = "Invalid API Key or insufficient permissions" if status in (401, 403) else "API request failed"
            message = (data.get("msg") or data.get("message")) if isinstance(data, dict) else None
            if not isinstance(message, str):
                message = reason
            message = message.replace(self._api_key, "[REDACTED]")
            if isinstance(code, str):
                code = code.replace(self._api_key, "[REDACTED]")
            raise BrowserActError(
                f"BrowserAct HTTP {status}: {reason}; {message} (code={code})",
                status_code=status,
                code=code,
            ) from None
        return data

    def validate_credentials(self) -> None:
        data = self._get("/v3/bots", {"page": 1, "limit": 1})
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise BrowserActError("BrowserAct returned an invalid Bot list response.")

    def _list_pages(self, path: str, limit: int) -> list[dict]:
        page, total_pages = 1, 1
        items = []
        while page <= total_pages:
            data = self._get(path, {"page": page, "limit": limit})
            if (
                not isinstance(data, dict)
                or not isinstance(data.get("items"), list)
                or any(not isinstance(item, dict) for item in data["items"])
                or type(data.get("page")) is not int
                or data["page"] != page
                or type(data.get("total_pages")) is not int
                or data["total_pages"] < 0
                or (data["total_pages"] == 0 and bool(data["items"]))
                or (data["total_pages"] > 1 and not data["items"])
            ):
                raise BrowserActError("BrowserAct returned invalid list pagination. Refresh and try again.")
            if page > 1 and data["total_pages"] != total_pages:
                raise BrowserActError("BrowserAct list pagination changed. Refresh and try again.")
            items.extend(data["items"])
            total_pages = data["total_pages"]
            page += 1
        return items

    def list_bots(self) -> list[dict]:
        return [
            item for item in self._list_pages("/v3/bots", 100)
            if item.get("published_at")
        ]

    def list_templates(self) -> list[dict]:
        return self._list_pages("/v3/bots/templates", 500)

    def get_definition(self, source: str, target_id: str) -> dict:
        if not isinstance(target_id, str) or not re.fullmatch(r"[0-9]+", target_id):
            raise BrowserActError("Select a valid Bot or template ID.")
        path = "/v3/bots" if source == "bot" else "/v3/bots/templates"
        field = "bot_id" if source == "bot" else "template_id"
        detail = self._get(f"{path}/{target_id}")
        if not isinstance(detail, dict) or str(detail.get(field)) != target_id:
            raise BrowserActError("The target ID returned by BrowserAct does not match the selected target.")
        return detail

    def create_run(self, source: str, target_id: str, inputs: dict):
        path = "/v3/bots" if source == "bot" else "/v3/bots/templates"
        body = {"input": inputs}
        return self._request("POST", f"{path}/{target_id}/runs", body=body)

    def get_task_status(self, task_id: str, *, timeout=30):
        return self._get(f"/v3/bots/runs/{task_id}/status", timeout=timeout)

    def get_task(self, task_id: str, *, timeout=30):
        return self._get(f"/v3/bots/runs/{task_id}", timeout=timeout)
