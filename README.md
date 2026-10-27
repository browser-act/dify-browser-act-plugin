# BrowserAct for Dify

Run BrowserAct Bots and official templates from a Dify workflow, and wait for
the result inside the node.

BrowserAct is a hosted browser-automation service. You build or choose a Bot in
BrowserAct, then this plugin starts a task with your inputs and returns the task
result as JSON.

## Tools

| Tool | What it runs |
| --- | --- |
| **Run My Bot** | A published Bot in your BrowserAct account |
| **Run Official Template** | A public template from the BrowserAct template library |

Both tools share the same connection, parameters and output shape.

## Requirements

- Dify Community Edition or Dify Cloud.
- A BrowserAct account with at least one published Bot, or access to official
  templates.
- A BrowserAct API Key.
- Outbound HTTPS access to `api.browseract.com`. The host is fixed; the plugin
  does not accept a custom endpoint.

## Install

1. Install **BrowserAct** from the Dify Marketplace, or upload the `.difypkg`
   file from the Plugins page.
2. Open **Plugins → BrowserAct → Authorize** and paste your BrowserAct API Key.
3. Add a **Run My Bot** or **Run Official Template** node to a workflow.

The API Key is stored by Dify as the Provider credential and sent to BrowserAct
as a Bearer token. Saving the credential validates it against your Bot list; it
does not start a task.

## Configure a node

| Field | Description |
| --- | --- |
| **Operation** | `Run Bot` executes and waits for the result. `View Parameters` only reads the input definition. Defaults to `Run Bot`. |
| **Bot** / **Template** | The target to run. The list loads from BrowserAct and can be searched by typing. |
| **Wait Timeout (seconds)** | How long the node waits. Defaults to 600. Used only when running. |
| **Custom Parameters JSON** | Input values for the Bot. Accepts a parameter object, `{}`, or the full output copied from `View Parameters`. |

### Find the right input parameters

1. Set **Operation** to `View Parameters` and run the node.
2. Open **LAST RUN** and copy the full output.
3. Paste it into **Custom Parameters JSON** and edit the values inside `json[0]`.
4. Switch **Operation** back to `Run Bot`.

Objects merge recursively and arrays are replaced. Explicit `false`, `0` and
empty strings are kept. Inputs are validated against the Bot's input schema
before the task is created.

## Output

The node returns the complete task detail as one JSON message, plus named
variables for downstream nodes:

`task_id`, `status`, `bot_id`, `bot_name`, `bot_type`, `created_at`,
`finished_at`, `input`, `output`, `output_files`, `download_files`,
`files_expires_at`, `log_detail_url`, `task_failure_info`, `steps`,
`live_url_info`, `credit`.

Notes:

- `task_id` and `bot_id` are strings, so large numeric IDs keep their digits.
- `output` keeps the Bot's original JSON type. Bots do not share a fixed result
  schema, so typed pickers may show it as unknown; select the complete `json`
  variable or use a Code node when you need a specific type.
- `output_files` is keyed by format (`csv`, `json`, `markdown`, `md`, `xml`).
  Each entry has a temporary download URL. Inline results are limited to 5 MB;
  generated files are limited to 100 MB each.
- File URLs are temporary. Use them before `files_expires_at`; the plugin does
  not download, re-upload or extend them.

## Waiting, timeout and errors

- The wait starts when the task is created and defaults to 600 seconds.
- On timeout the node fails and keeps `task_id`. The plugin stops polling but
  does not cancel the remote task; BrowserAct may cancel it later according to
  its own heartbeat and scheduling policy.
- A `pausing` or `paused` task ends the wait immediately and is reported as a
  failure with the current state and `task_id`. Paused tasks are not resumed
  automatically.
- `failed` and `canceled` tasks report the failure information returned by the
  API.
- Task creation is never retried automatically, so an unclear response cannot
  create a duplicate task.
- HTTP requests use a 30-second inactivity timeout, clamped to the remaining
  wait budget.

## Limitations

- A node runs one task and waits for it; long tasks can exceed the single-step
  timeout of the Dify editor even though the task keeps running in the
  background.
- Large outputs may not stream to the editor reliably. Check the run history
  before retrying.
- The task result is not converted or reshaped. Downstream typing depends on
  the Bot's own output.
- A disconnected browser page does not stop the plugin from polling, and does
  not prove that polling stopped.

## Data and privacy

The plugin sends your API Key and task inputs to BrowserAct and returns task
results to Dify. It keeps a small in-memory cache of list options for 60 seconds
and writes nothing to disk. See [PRIVACY.md](PRIVACY.md) for the full data flow.

## Documentation

- Integration overview: <https://docs.browseract.com/integrations/integration-overview>
- API reference: <https://docs.browseract.com/workflow/api-reference>

## Source and support

- Source repository: <https://github.com/browser-act/dify-browser-act-plugin>
- Contact: <service@browseract.com>
