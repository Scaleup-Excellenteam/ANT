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

## Part B: semantic search with Gemini Embeddings

The optional semantic mode finds corpus sentences by meaning, including queries
that use different words. It uses Google's `gemini-embedding-001` model with
`RETRIEVAL_DOCUMENT` for corpus sentences and `RETRIEVAL_QUERY` for user input.
The original sentence, source path, and line offset are retained in every result.
Cosine similarity is labeled `semantic_similarity`; it is not Part A's edit score.

The normal `python -m src.main` command and all Part A behavior remain unchanged.

### Setup

Create a Gemini API key in Google AI Studio. Store it in the process environment,
never in this repository:

```powershell
$env:GEMINI_API_KEY = "your-key"
```

Install dependencies and build a small cost-controlled demo index first:

```powershell
python -m pip install -r requirements.txt
python -m src.semantic.build_index --limit 50 --batch-size 50
```

The free tier may count each embedded sentence as a request even when the SDK sends a
batch, so start with 50. Check current Gemini API quotas and pricing before increasing
or removing `--limit`. Building the
full index sends every corpus sentence to the external API and may take time or incur
cost. The generated `semantic_index.pickle` and `.env` files are ignored by Git.

Run semantic search:

```powershell
python -m src.main --semantic
```

Example: a query such as `automobile running out of gas` can retrieve a corpus
sentence such as `The car needs fuel`, even without an exact substring match.

### Data flow and failure behavior

1. The offline builder loads the Part A corpus and sends sentence batches to Gemini.
2. It normalizes and stores the returned vectors together with real source metadata.
3. Semantic mode embeds the query, computes cosine similarity locally, and returns
   the top five original corpus sentences.
4. Missing indexes, keys, timeouts, quota errors, unavailable service, malformed
   responses, and incompatible vector dimensions produce a clear message. The basic
   autocomplete mode remains available without `--semantic`.

Only non-private test/corpus text should be sent to the external service. The index is
an exact local pickle cache: load only the file produced by this application.

### Design limitations

- The simple local scan is intended for a course demo. A large production corpus
  should use an approximate-nearest-neighbor vector database.
- Corpus updates require rebuilding the semantic index.
- Relevance depends on the embedding model and corpus coverage; semantic similarity
  is not proof that a result is factually correct.

## Team decisions currently used by this initial workspace

- Empty input: print a message and do not search.
- Fewer than 5 matches: display only the valid matches.
- Zero matches: print `No suggestions found.`.
- Equal score: alphabetical order by completed sentence.
- `#`: reset the accumulated query.
- Query stays accumulated after every search so the user can continue typing.
