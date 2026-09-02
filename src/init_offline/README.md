# init_offline — Member 1 deliverable (Init/Offline Builder)

Implements the offline phase per `SPEC_MEMBER_1_INIT.md`, using the **hybrid index**
architecture (word inverted index + trigram index + vocabulary trie) agreed after reviewing
and rejecting the original word-boundary-suffix Trie design (too slow to build on the real
corpus, and structurally unable to find matches that fall entirely inside a word).

## Public API (the hand-off contract with Member 2)

```python
from init_offline import CorpusIndex, load_or_build_index, normalize

index = load_or_build_index()          # builds from ../../resources/Archive.zip, or loads the cache
query = normalize(user_typed_text)     # Member 2 MUST use this exact function
```

### `CorpusIndex` — the one object Member 2 needs

| Method | Returns | When to use it |
|---|---|---|
| `get_sentence(sentence_id)` | `SentenceRecord` (original_text, normalized_text, source_path, offset) | Once you have a candidate `sentence_id`, fetch its full record to build `AutoCompleteData` and to verify/score against `original_text`/`normalized_text`. |
| `word_candidates(word)` | `List[int]` sentence_ids | **Fast path.** Look up an anchor word (usually the first or a rarer word of the query) here first. Empty list is a normal outcome, not an error. |
| `trigram_candidates(normalized_text)` | `Set[int]` sentence_ids | **Correctness backstop.** Finds sentences sharing a trigram with `normalized_text` — this is what catches matches that fall entirely inside a word (no shared whole word). Only a *completeness guarantee* for `len(normalized_text) >= 6`. |
| `short_query_candidates(normalized_query)` | `Set[int]` sentence_ids | Use instead of `trigram_candidates` when `len(normalized_query) <= 5` (see below). Raises `ValueError` if called with a longer query — that's a signal you called the wrong method, not a real error case. |
| `fuzzy_vocabulary_lookup(word, max_edits=1)` | `List[str]` real vocabulary words | Use when `word_candidates(word)` comes back empty and you suspect the query's one allowed edit landed inside your anchor word itself. Returns real corpus words within `max_edits` edits of `word` — feed each result back into `word_candidates`. |

### `SentenceRecord` fields
- `sentence_id: int` — dense index, matches what the indexes return.
- `original_text: str` — untouched, punctuation intact. Use this for `AutoCompleteData.completed_sentence`.
- `normalized_text: str` — precomputed once at build time with `normalize()`. Compare your normalized query against this, never against `original_text`.
- `source_path: str`, `offset: int` — copy directly into `AutoCompleteData`.

## Why this replaced the original Trie design

The original design inserted every word-boundary suffix of every corpus line into a character
trie. Two problems, confirmed while building it:
1. **Too expensive.** A real build against the ~122MB corpus did not finish in over 10 minutes
   and had to be killed — insertion cost scales with `words_per_line × remaining_line_length`,
   which blows up on a corpus with many long lines.
2. **Not even fully correct.** It only indexed suffixes starting at word boundaries, so it
   could never find a match that falls entirely inside a word (e.g. "symmetric" inside
   "asymmetric") — which the assignment's own wording permits ("the text is a substring of the
   sentence — this includes the start, middle, or end of the sentence").

The hybrid design fixes both: build is linear in corpus size (confirmed — see benchmark
below), and the trigram index is specifically there to catch what the word index cannot.

## Why the trigram index guarantees correctness (for queries >= 6 chars)

Trigram matching here is **set-based**, not position-based: "does this exact 3-character
sequence appear anywhere in the sentence?" A single edit (substitution, insertion, or
deletion) can only corrupt trigrams that literally overlap the edited character — at most 3 of
them, regardless of edit type (insertion/deletion just shifts *where* later characters sit,
which set-membership doesn't care about). So any query with more than 3 trigrams — i.e.
**6 or more normalized characters** — is guaranteed to keep at least one trigram that exactly
matches the true target region, guaranteeing the sentence is found as a candidate.

## Short-query fallback (normalized lengths 1–5)

Below 6 characters, the guarantee above doesn't hold (too few trigrams to guarantee a
survivor; below 3 characters there are no trigrams at all). `short_query_candidates()` covers
this by combining:
1. Whatever trigrams *do* exist for the query (0 trigrams if length < 3, else `length - 2`).
2. Every sentence containing a vocabulary word that itself contains the query as a substring
   anywhere (`vocabulary.words_containing_substring`) — this catches both the "too short for
   any trigram" case and reinforces the mid-word case for short queries.

**Member 2: call `short_query_candidates` instead of `trigram_candidates` whenever
`len(normalized_query) <= 5`.** `CorpusIndex.trigram_candidates` does not raise or warn if
called with a short query — it will just silently under-cover, so this is a real contract to
follow, not a suggestion.

## What Member 1 owns vs. what stays Member 2's job

Unchanged from `SPEC_MEMBER_1_INIT.md` / `SPEC_MEMBER_2_MATCHING.md` — only the underlying
structure changed, not the responsibility split:

- **Member 1 (this module):** corpus loading, normalization (once, at build time), building
  all three indexes, and the query primitives above.
- **Member 2 (Yazan):** normalizing the user's query with the same `normalize()`, choosing
  anchor words/trigrams (including picking rarer ones when a candidate set is too large — see
  caveat below), calling `fuzzy_vocabulary_lookup` when an anchor word might contain the typo,
  running the actual bounded edit-distance-1 substring verification against `original_text`/
  `normalized_text`, computing the score, and doing top-5 selection + alphabetical tie-break.

## Known caveat: trigram/word selectivity on a small alphabet

Corpus text is normalized down to lowercase letters, digits, and spaces (~37 symbols), so the
space of distinct trigrams is small (at most 37³ ≈ 50,000). Common trigrams (e.g. "the",
" an") can appear in a large fraction of all sentences, just like common words do in the word
index. **Member 2 should pick the rarest word/trigram among the query's options as the anchor**
(`trigram_index.postings_size(trigram)` / comparing `len(word_candidates(word))` across
candidate words) rather than always using the first token, to keep candidate sets small in the
common case. This is a real, expected characteristic of this design, not a bug — verification
itself stays cheap either way since it's a direct scan of a short query against a short
candidate sentence.

## Memory optimization: postings stored as `array.array`, not `set`/`list`

The first working version of this design stored word/trigram postings as `set[int]` (needed
during accumulation for O(1) dedup as sentences stream in) and left them as sets in the
finished index too. Measured on the real corpus, that cost ~5.6GB peak RSS — too high.

The fix: a `set` is only needed *while building*. Once the corpus is fully processed, every
posting list is fixed and only ever iterated/unioned, never probed element-by-element — so
both `word_index.py` and `trigram_index.py` now finalize each bucket as a sorted
`array.array('L', ...)` (raw packed 4-byte integers, no per-element Python object, no hash
table) instead of a `set`. This is a straight memory win with no correctness change:
- `WordInvertedIndex.candidates()` still returns `List[int]` — unchanged contract.
- `TrigramIndex.candidates_for_trigram()` / `candidates_for_text()` still return `Set[int]` —
  unchanged contract. Conversion happens at these API boundaries; internal storage is an
  implementation detail Member 2 never has to know about.
- Query-time union code barely changed: `set.update()` accepts an `array.array` directly, so
  `result.update(self._postings.get(trigram, ()))` works exactly like it did with sets.

See the commit introducing this change for the measured before/after build time, peak memory,
and pickle size.

## Persistence

```python
from init_offline import load_or_build_index, save_index, load_index, CorpusIndex

index = load_or_build_index()                    # cache-aware: builds once, reuses after
save_index(index, "my_cache.pickle")              # explicit save
index = load_index("my_cache.pickle")             # explicit load
index = CorpusIndex.build_from_zip("Archive.zip")  # force a fresh build, no caching
```

Plain `pickle` — this is a pure in-process Python structure (dict + list of dataclasses + a
small trie), no cross-language or cross-version distribution need, so nothing fancier
(JSON/SQLite/custom binary) buys anything here.

## ZDT: zero-downtime snapshot publishing (`snapshot_store.py`)

The single flat `corpus_index.pickle` above is fine for one-shot local runs, but a live
service can't safely rebuild it in place (a reader could open it mid-write) and has no way
to pick up a new corpus without restarting. `snapshot_store.py` extends the same `pickle`
persistence with versioning and an atomic hand-off:

```python
from init_offline import build_snapshot, publish_snapshot, get_current_version, load_snapshot

# Build-then-publish in one call -- validates (rejects an empty build) before flipping the
# pointer, so CURRENT only ever names a snapshot that finished building successfully.
version = publish_snapshot(zip_path="new_source.zip", snapshots_dir="/srv/shared/corpus_snapshots")

# Anywhere (same box or a shared/remote filesystem) that reads the pointer:
current = get_current_version("/srv/shared/corpus_snapshots")   # e.g. "20260101T120000Z-3f9a2b1c8e4d"
index = load_snapshot("/srv/shared/corpus_snapshots", current)
```

Every build gets its own immutable directory (`<snapshots_dir>/<version>/corpus_index.pickle`);
publishing a new one never overwrites or deletes an older, possibly still-in-use snapshot.
`CURRENT` is a one-line pointer file, written via write-to-temp-file-then-`os.replace` (POSIX
`rename(2)`) so it is always either the old, complete value or the new, complete value — never
truncated mid-read.

`src/init_offline/build_snapshot_cli.py` is the operator-facing command for this:

```bash
python -m src.init_offline.build_snapshot_cli --zip resources/Archive.zip
python -m src.init_offline.build_snapshot_cli --list
python -m src.init_offline.build_snapshot_cli --rollback 20260101T120000Z-3f9a2b1c8e4d
```

See the top-level README's "Zero-downtime snapshot publishing" section for how the online
side (`matching.completions.HotReloadableIndex`) polls this and hot-swaps live.

## Running the tests

```bash
python -m pytest tests/test_init_offline/            # fast unit + light integration tests
RUN_SLOW_TESTS=1 python -m pytest tests/test_init_offline/test_integration_real_corpus.py  # + full build
```
