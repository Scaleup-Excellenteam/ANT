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
- `src/main.py` only composes those components.

## Requirements

- Python 3.9 or newer
- The dependencies in `requirements.txt`
- `resources/Archive.zip` for corpus mode
- A Gemini API key only for AI mode

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
$env:GEMINI_MODEL="gemini-2.5-flash"  # optional
```

bash/zsh:

```bash
export GEMINI_API_KEY="your-key"
export GEMINI_MODEL="gemini-2.5-flash"  # optional
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
Gemini model: gemini-2.5-flash; response time: <measured> ms; no corpus source, offset, or Part A score.
1. [AI-GENERATED] Thank you for taking the time to review our proposal.
...
```

Gemini output is nondeterministic, so exact sentences can differ between runs. The
automated tests use a deterministic fake client and validate the interface and labels.

## Failure handling

- Missing API key: AI mode explains the required setup; corpus mode continues
  to work.
- Timeout, quota, network, or service failure: the error is translated into a clear
  message, the query is preserved, and the user can retry or switch to corpus mode.
- Empty, malformed, duplicate, or prefix-breaking model output: it is rejected rather
  than displayed as a valid suggestion.
- Inputs are length-bounded to avoid accidental oversized requests.

The application uses Gemini's official HTTPS `generateContent` endpoint and sets a
15-second timeout to avoid waiting indefinitely. A failure does not trigger an
unbounded retry loop or a second billable request.

## Security, privacy, access, and cost

- `GEMINI_API_KEY` is read only from the environment and is never logged or committed.
- `.env` variants are ignored by Git; `.env.example` contains no secret.
- Only text entered while explicitly in AI mode is sent to Gemini.
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
- preservation of all Part A tests and behavior.

The feature metric is response time. Every successful Gemini response records and
displays its latency in milliseconds. Relevance is evaluated with the same prefix under
at least two distinct contexts and by confirming that each result begins with the prefix
and follows the selected context.

## Limitations and tradeoffs

- Gemini suggestions are generated content, not factual corpus matches.
- Quality and latency can vary between calls, models, quotas, and network conditions.
- The application does not automatically fall back from AI to corpus mode because that
  could silently change result meaning; it preserves the query and asks the user to
  switch explicitly.
- AI mode currently sends only the prefix and user context, not corpus documents.
- The existing Part A index is large and corpus searches can still be slow for common
  queries; that performance issue is separate from the Part B integration.
