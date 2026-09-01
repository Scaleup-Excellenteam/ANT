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

## Multilingual search mode

Part B adds an optional Translation mode:

```text
/translate  # translate user input to English before searching
/english    # return to normal English autocomplete
```

In Translation mode, the CLI sends the accumulated user query to Google Cloud
Translation, asks for English output, displays the translated English query, and
then passes only that translated English text into the existing Part A
autocomplete engine. If translation fails, the CLI prints a clear error and does
not search the original non-English query.

Google Cloud Translation uses Application Default Credentials. Do not store
credentials in this repository. For local runs, configure the environment before
starting the program:

```powershell
$env:GOOGLE_CLOUD_PROJECT = "your-project-id"
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\service-account.json"
```

Optional timeout override:

```powershell
$env:TRANSLATION_TIMEOUT_SECONDS = "10"
```

Normal English mode does not require Google credentials.

## Run tests

```bash
python -m pytest -q
```

## Team decisions currently used by this initial workspace

- Empty input: print a message and do not search.
- Fewer than 5 matches: display only the valid matches.
- Zero matches: print `No suggestions found.`.
- Equal score: alphabetical order by completed sentence.
- `#`: reset the accumulated query.
- Query stays accumulated after every search so the user can continue typing.
