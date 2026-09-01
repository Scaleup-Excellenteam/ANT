# AutoComplete Search System - Initial Team Integration

This branch combines the team's initial offline indexing, matching/scoring, and
CLI/serving implementations.

## Integrated pipeline

- `src/init_offline/` builds and caches the corpus index from `resources/Archive.zip`.
- `src/matching/` generates, verifies, scores, and ranks real completions.
- `src/cli.py` serves the results through the interactive CLI.
- `src/main.py` connects all three layers.

## Run immediately

From the project root:

```bash
python -m src.main
```

You can also run:

```bash
python src/main.py
```

The first real query builds `corpus_index.pickle` from the bundled corpus if no
cache exists. Later runs load that cache. Enter more text to extend the current
query, `#` to reset it, or `~` to exit.

## Run tests

```bash
python -m pytest -q
```

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

### Future satellite communication logging

`src.communication_logging.SatelliteCommunicationLogger` is a transport-agnostic
event helper for future server-to-satellite code. It uses the same centralized
handler and named `satellite.*` loggers. It measures ACK latency and connection
downtime with a monotonic clock and records retry, queue, delivery, bandwidth,
and byte-count metadata. It does not implement networking, queues, or compression.

```python
from src.communication_logging import SatelliteCommunicationLogger

communication_log = SatelliteCommunicationLogger()
communication_log.message_sent(421, priority="high")
communication_log.waiting_for_ack(421)
# Future transport waits for its ACK here.
communication_log.ack_received(421)
```

The helper intentionally accepts no message payload, API key, token, password,
or other credential arguments. Future transport code should pass identifiers and
metrics only.

## Team decisions currently used by this initial workspace

- Empty input: print a message and do not search.
- Fewer than 5 matches: display only the valid matches.
- Zero matches: print `No suggestions found.`.
- Equal score: alphabetical order by completed sentence.
- `#`: reset the accumulated query.
- Query stays accumulated after every search so the user can continue typing.
