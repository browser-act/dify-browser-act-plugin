class BrowserActError(Exception):
    """A credential-safe error that can be presented through the Dify SDK."""

    def __init__(
        self, message: str, *, status_code: int | None = None,
        code: int | str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class BrowserActTaskError(BrowserActError):
    def __init__(
        self, message: str, *, task_id: str, remote_status=None,
        status_code=None, code=None,
    ):
        super().__init__(f"{message}; task_id={task_id}.", status_code=status_code, code=code)
        self.task_id = task_id
        self.remote_status = remote_status
