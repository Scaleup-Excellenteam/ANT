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

## Team decisions currently used by this initial workspace

- Empty input: print a message and do not search.
- Fewer than 5 matches: display only the valid matches.
- Zero matches: print `No suggestions found.`.
- Equal score: alphabetical order by completed sentence.
- `#`: reset the accumulated query.
- Query stays accumulated after every search so the user can continue typing.
