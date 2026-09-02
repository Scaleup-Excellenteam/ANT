# AutoComplete Search System - Parts A and B

This project preserves the Part A corpus autocomplete engine and adds an explicit
Part B context-aware completion mode powered by the Google Gemini API.

## User need and feature value

Part A can only return sentences that already exist in `Archive.zip`. That is useful
for retrieval, but it cannot help a user draft a new sentence for a particular domain
or style. Part B adds an opt-in AI mode that generates full-sentence continuations from:

- the text typed by the user; and
- a user-selected context such as `formal email`, `technical documentation`, or
  `friendly customer support`.

The mode is always visible. Gemini output is labeled `[AI-GENERATED]` and is never
given a corpus source, line offset, or Part A edit score.

## Architecture and data flow

The three concerns remain replaceable and independently testable:

```text
User interface (src/enhanced_cli.py)
        |-- CORPUS mode --> Part A matching engine --> real corpus results
        `-- AI mode -----> Gemini adapter ----------> generated suggestions
```

- `src/init_offline/` builds and loads the corpus index.
- `src/matching/` retrieves, verifies, scores, and ranks Part A results.
- `src/contextual/gemini_client.py` owns Gemini REST configuration, requests,
  structured-response validation, timeouts, and stable error translation.
- `src/enhanced_cli.py` owns modes, context, commands, and display formatting.
- `src/protobuf_api/` defines the shared wire contract, generated binding, adapter,
  and binary round-trip client.
- `src/main.py` only composes the interactive components.

## Requirements

- Python 3.9 or newer
- The dependencies in `requirements.txt`
- `resources/Archive.zip` for corpus mode
- A Gemini API key only for AI mode
- Google Cloud project and Application Default Credentials only for Translation mode

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Create an API key by following the official
[Gemini API setup guide](https://ai.google.dev/gemini-api/docs/get-started), then
set it in your shell. Never commit the value.

PowerShell:

```powershell
$env:GEMINI_API_KEY="your-key"
$env:GEMINI_MODEL="gemini-3.6-flash"  # optional
```

bash/zsh:

```bash
export GEMINI_API_KEY="your-key"
export GEMINI_MODEL="gemini-3.6-flash"  # optional
```

The application reads process environment variables; it does not automatically load
`.env` files. `.env.example` is only a safe configuration reference.

## Run

From the project root:

```bash
python -m src.main
```

Direct script execution is also supported:

```bash
python src/main.py
```

The CLI starts in `CORPUS` mode, so Part A works without a Gemini key.

### Commands

- `/mode corpus` - use the original Part A corpus search and score.
- `/mode ai` - use context-aware Gemini generation.
- `/translate` - translate input to English, then search the corpus.
- `/english` - return to regular English corpus mode.
- `/context <domain or style>` - set the AI context.
- `/context` - show the current context.
- `#` - reset the current query without changing mode or context.
- `~` - quit.
- `/help` - show the command summary.

## End-to-end demonstration

Before the improvement, corpus mode only retrieves existing archive lines:

```text
[CORPUS] Enter more text: Thank you for
Here are ... suggestions:
1. <original corpus sentence> (<real path>:<offset>, score=<Part A score>)
```

After switching to AI mode, the same prefix can be completed for a chosen use case:

```text
[CORPUS] Enter more text: /mode ai
Mode changed to AI. Query reset.
[AI | context=general, clear English] Enter more text: /context concise professional email
AI context updated: concise professional email
[AI | context=concise professional email] Enter more text: Thank you for
Here are 5 AI-generated suggestions:
Gemini model: gemini-3.6-flash; response time: <measured> ms; no corpus source, offset, or Part A score.
1. [AI-GENERATED] Thank you for taking the time to review our proposal.
...
```

Gemini output is nondeterministic, so exact sentences can differ between runs. The
automated tests use a deterministic fake client and validate the interface and labels.

## Multilingual search mode

Translation mode converts an accumulated non-English query to English with Google
Cloud Translation and then searches the existing Part A corpus with the translated
text. The translated English query is shown before the suggestions.

```text
/translate  # enter Translation mode and reset the query
/english    # return to English corpus mode and reset the query
```

Google Cloud Translation uses Application Default Credentials. Do not store
credentials in this repository. Configure them before starting the application:

```powershell
$env:GOOGLE_CLOUD_PROJECT="your-project-id"
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\service-account.json"
```

Optional timeout override:

```powershell
$env:TRANSLATION_TIMEOUT_SECONDS="10"
```

Corpus and AI modes remain available without Translation credentials.

## Shared Protocol Buffers interface

`src/protobuf_api/autocomplete.proto` defines one language-neutral request/response
contract for both corpus and AI searches. Each suggestion uses a Protobuf `oneof` so
another client receives either corpus metadata (`source_text`, `offset`, and `score`)
or AI metadata (`model`) without guessing from display text.

The checked-in `autocomplete_pb2.py` is generated by the Protobuf compiler and is used
by the adapter and demo; it is not a handwritten replacement for generated code.
Regenerate it after editing the schema:

```bash
python -m grpc_tools.protoc -I src/protobuf_api --python_out=src/protobuf_api src/protobuf_api/autocomplete.proto
```

Demonstrate real binary encoding and decoding with the existing corpus engine:

```bash
python -m src.protobuf_api.demo --query "to pe" --mode corpus --max-results 2
```

Or, after setting `GEMINI_API_KEY`, use the same contract with AI mode:

```bash
python -m src.protobuf_api.demo --query "Thank you for" --mode ai --context "concise professional email" --max-results 3
```

The integration enables a Python, Java, C#, C++, or other Protobuf client to generate
bindings from the same `.proto` file and exchange compatible request/result bytes.
Protobuf defines and serializes those bytes; it is not the communication mechanism.
A deployment may carry them over HTTP, gRPC, a queue, a socket, or a file.

## Failure handling

- Missing API key: AI mode explains the required setup; corpus mode continues
  to work.
- Timeout, quota, network, or service failure: the error is translated into a clear
  message, the query is preserved, and the user can retry or switch to corpus mode.
- Empty, malformed, duplicate, or prefix-breaking model output: it is rejected rather
  than displayed as a valid suggestion.
- Inputs are length-bounded to avoid accidental oversized requests.

The application uses Gemini's official HTTPS `generateContent` endpoint, a
30-second timeout, and at most one retry for malformed output or transient failures.
Permanent client errors are not retried.

## Security, privacy, access, and cost

- `GEMINI_API_KEY` is read only from the environment and is never logged or committed.
- `.env` variants are ignored by Git; `.env.example` contains no secret.
- Only text entered while explicitly in AI mode is sent to Gemini.
- Only text entered in Translation mode is sent to Google Cloud Translation.
- Do not send private or sensitive information without authorization.
- Check current Gemini API permissions, quotas, and
  [pricing](https://ai.google.dev/gemini-api/docs/pricing) before a live demo. Paid
  usage must be coordinated with the project mentors.

## Tests and evidence

Run everything:


```bash
python -m pytest -q
```

The tests cover:

- Gemini structured-response success and validation;
- missing credentials, service failure, malformed output, duplicates, and bad input;
- visible modes, context changes, reset, exit, and unknown commands;
- generated-content labeling with no fabricated corpus metadata;
- preservation of all Part A tests and behavior;
- Protobuf request/response serialization, corpus and AI mapping, and invalid bytes; and
- Hebrew/Arabic translation flow, mode switching, and Translation API failures.

The feature metric is response time. Every successful Gemini response records and
displays its latency in milliseconds. Relevance is evaluated with the same prefix under
at least two distinct contexts and by confirming that each result begins with the prefix
and follows the selected context.

## Logging

Application logging is configured once at startup and written to `logs/app.log`.
The default level is `INFO`; use `DEBUG` for candidate, verification, ranking,
and timing details:

```powershell
$env:AUTOCOMPLETE_LOG_LEVEL = "DEBUG"
python -m src.main
```

Set `AUTOCOMPLETE_LOG_FILE` to override the log path. Log files rotate at 5 MB,
with three backups (`app.log.1` through `app.log.3`). Generated logs are ignored
by Git. API keys, tokens, and environment-variable values are never logged.

## Limitations and tradeoffs

- Gemini suggestions are generated content, not factual corpus matches.
- Quality and latency can vary between calls, models, quotas, and network conditions.
- The application does not automatically fall back from AI to corpus mode because that
  could silently change result meaning; it preserves the query and asks the user to
  switch explicitly.
- AI mode currently sends only the prefix and user context, not corpus documents.
- The existing Part A index is large and corpus searches can still be slow for common
  queries; that performance issue is separate from the Part B integration.

## Zero-downtime snapshot publishing (ZDT)

The corpus index used to be a single flat `corpus_index.pickle`, built once and read for the
life of the process (`init_offline.load_or_build_index`, still the default when nothing below
is set up). That works for a one-shot local run, but a live service has no safe way to pick
up a new or updated corpus without either overwriting the file a reader might be mid-load on,
or restarting the process outright.

`src/init_offline/snapshot_store.py` decouples offline building from online serving through
the filesystem, so a new data source can be published to an already-running service, live,
remotely, with no restart and no dropped requests:

- Every offline build writes to its own immutable, versioned directory —
  `<snapshots_dir>/<timestamp>-<content-hash>/corpus_index.pickle` — never overwriting a
  previous, possibly still-in-use snapshot.
- A build only becomes "live" once a small `CURRENT` pointer file inside `snapshots_dir` is
  flipped to it, and only after the build validates (rejects an empty/zero-sentence corpus).
  The pointer is written via write-to-temp-file-then-`os.replace` (POSIX `rename(2)`), which
  is atomic within one filesystem — a reader always sees a complete, valid version id.
- The online side, `matching.completions.HotReloadableIndex`, is what `get_best_k_completions`
  actually calls through. It polls `CURRENT` at most once every
  `ZDT_RELOAD_CHECK_INTERVAL_SECONDS` (default 2s), and only when the pointer names a version
  it hasn't loaded yet does it load that snapshot and swap its in-memory reference — a single
  attribute assignment, atomic under the GIL. A query already in progress keeps the
  `CorpusIndex` object reference it already grabbed, so the swap never affects an in-flight
  request.

Add a new data source with the service already running, no restart:

```bash
# 1. Build the new corpus zip (or point at a shared/remote path this snapshots_dir already
#    resolves to -- local disk, NFS, a synced cloud-storage mount, anything with normal
#    filesystem rename semantics works).
# 2. Build + validate + publish in one step:
python -m src.init_offline.build_snapshot_cli --zip new_source.zip \
    --snapshots-dir /srv/shared/corpus_snapshots

# 3. Within ZDT_RELOAD_CHECK_INTERVAL_SECONDS, every running `python -m src.main` (or any
#    other process calling get_best_k_completions) polling that same --snapshots-dir starts
#    answering queries from the new snapshot -- live, with zero downtime.
```

List published versions or roll back to a previous one without rebuilding:

```bash
python -m src.init_offline.build_snapshot_cli --list --snapshots-dir /srv/shared/corpus_snapshots
python -m src.init_offline.build_snapshot_cli --rollback 20260101T120000Z-3f9a2b1c8e4d \
    --snapshots-dir /srv/shared/corpus_snapshots
```

By default `snapshots_dir` is `.runtime/corpus_snapshots` next to the repo (override with
`ZDT_SNAPSHOTS_DIR`); this is git-ignored local/deployment state, not checked-in data.

### Limitations

- This repo's offline builder (`CorpusIndex.build_from_zip`) still builds from one zip
  archive at a time. "Adding a data source" means publishing a new zip that contains the
  full corpus you want served (old content plus the new addition) as a new version — there
  is no multi-archive merge step; that is a natural next step but out of scope here.
- The offline build and the online service must load pickles produced under the same Python
  import convention (both invoked as `python -m src...` from the repo root, as the README
  already recommends) — this is a pre-existing constraint of `CorpusIndex`'s plain-`pickle`
  persistence, unchanged by this feature.
- `HotReloadableIndex`'s check-then-load is not additionally locked, so two threads racing
  the same reload window could both load the same new snapshot once (correct, just
  redundant work). The one process this repo actually runs today (`python -m src.main`) is
  single-threaded, so this does not occur in practice; a future concurrent server adopting
  this class should add a lock around `_refresh_if_due` if that changes.
- This is zero **downtime**, not zero **latency spike**: the service stays available and
  existing requests keep serving from the old index during a swap, but the one request
  whose `_refresh_if_due` call detects the new version loads it synchronously and may see
  several seconds of added latency at this corpus's current size. Making that load
  asynchronous/background is a possible future improvement, not implemented here.
