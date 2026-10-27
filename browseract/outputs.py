"""Stable named run outputs; the complete API detail remains in json[0]."""

RUN_OUTPUT_FIELDS = (
    "task_id", "log_detail_url", "bot_id", "bot_type", "bot_name", "status",
    "created_at", "finished_at", "input", "task_failure_info", "output",
    "output_files", "download_files", "files_expires_at", "steps", "live_url_info", "credit",
)


def run_output_variables(detail: dict) -> dict:
    values = {name: detail[name] for name in RUN_OUTPUT_FIELDS if name in detail}
    for name in ("task_id", "bot_id"):
        if name in values and values[name] is not None:
            values[name] = str(values[name])
    return values
