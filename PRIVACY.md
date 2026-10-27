# BrowserAct for Dify: Data Handling

Updated: 2026-10-27. This notice describes version 0.0.9 of the plugin. It
covers the plugin code, not the separate Dify and BrowserAct services.

## Credentials and destinations

Dify supplies the BrowserAct API Key configured in the Provider connection. The
plugin sends it as an Authorization Bearer header over HTTPS to the fixed host
`api.browseract.com`. It does not offer a custom API host and does not follow
redirects. Every API request also carries `api-channel-ak: difyak`, which tells
BrowserAct that the call came from Dify; it does not replace the user's key and
does not add another recipient.

Credential validation reads the Bot list and does not start a task.

The plugin code does not write credentials to files and does not intentionally
log the key. API error messages redact the configured key. The option cache
described below indexes credentials by a SHA256 digest rather than retaining the
raw key; the SDK still supplies credentials in memory for authenticated calls.
Credential storage, workflow history and infrastructure logging in Dify or
BrowserAct are controlled by those services and their operators.

## Data processed

Dynamic selectors request Bot and template names and IDs from BrowserAct, and
return those choices to Dify. **View Parameters** reads the selected input
definition and returns explicitly declared default values to Dify; it does not
submit a task.

**Run Bot** sends the selected target ID and the merged business input to
BrowserAct. The plugin polls the created task and returns its full detail object
to Dify, including business output, task metadata, log links and temporary file
links. It does not download or re-upload result files. Returned values and
defaults may contain sensitive business data; downstream Dify nodes receive the
output the workflow is configured to use.

Run Bot also returns selected task fields as named Dify workflow variables while
retaining the full JSON detail. This adds no new recipient or API request.

## Retention and task lifecycle

The plugin reuses successful Bot and template selector options in process memory
for 60 seconds. Entries contain names and IDs, an API key digest, the SDK user ID
and the option source; different keys, users and sources are isolated. At most
128 option sets are retained. Expired sets are not reused and are removed on a
later cache access or eviction; process termination clears them as well. The
cache is not persisted. Failed list loads, input definitions, runtime checks,
task inputs and task results are not cached.

Other request data is held in memory while handling a call. The plugin adds no
database, persistent result store or independent analytics endpoint. This does
not delete or prevent storage of inputs, results or credentials by Dify,
BrowserAct, their SDK and runtime infrastructure, or configured downstream
tools. Those services' policies and deployment settings govern their storage.

A waiting timeout or query error stops plugin polling and retains `task_id`. The
plugin sends no cancellation request and does not resume paused tasks. Successful
status and detail queries refresh the task heartbeat on the BrowserAct side; once
queries stop, BrowserAct may cancel the task after its heartbeat expires,
according to its configuration and scheduler. A disconnected browser page does
not necessarily stop backend polling.

Temporary file links returned with a task should be treated as access-bearing
URLs and used before their reported expiry. The plugin does not extend their
validity.

## Third parties

The only third party that receives plugin data is BrowserAct, at
`api.browseract.com`, which performs the browser automation and stores the task
record. BrowserAct's privacy policy is published at
<https://www.browseract.com/privacy-policy>. Dify stores the credential and the
workflow run history in the user's own Dify deployment. No other service is
contacted by the plugin.
