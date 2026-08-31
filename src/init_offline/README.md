# init_offline — Member 1 deliverable (Init/Offline Builder)

Implements the offline phase described in `SPEC_MEMBER_1_INIT.md`. This module reads the
corpus (`Archive.zip`) and builds a search structure that the Matching phase (Member 2, Yazan)
queries to find candidate sentences for `get_best_k_completions`.

## Public API (the hand-off contract with Member 2)

```python
from init_offline import build_trie_from_zip, load_or_build_trie, normalize, Trie, TrieNode, SentenceRef

trie = load_or_build_trie()          # builds from ../../Archive.zip, or loads a cached pickle
node = trie.walk_exact(normalize(query))   # exact character descent (no typo tolerance)
refs = trie.collect_sentence_refs(node)    # -> List[SentenceRef] reachable from that node
```

- **`SentenceRef(original_text, source_path, offset)`** — one corpus line. `original_text`
  keeps punctuation/casing intact for display; `source_path` and `offset` are what Member 2
  should copy directly into `AutoCompleteData.source_text` / `.offset`.
- **`normalize(text) -> str`** — the *only* normalization function. Corpus text is normalized
  with this before being inserted into the trie. **Member 2 must call this exact same function
  on the user's typed query** before doing any trie traversal, or characters won't line up.
- **`Trie`** — character-level trie built over every word-boundary suffix of every corpus line
  (see `trie.py` module docstring for the full rationale). Traversal primitives for Member 2:
  - `trie.root` / `TrieNode.children: Dict[str, TrieNode]` — for manual/fuzzy descent
    (substitutions, skips, retries — however the typo-tolerant DFS is implemented).
  - `trie.walk_exact(prefix, node=None)` — exact-match descent from any node, no typo tolerance.
  - `trie.collect_sentence_refs(node)` — gather every `SentenceRef` reachable under a node.
    Needed once your query is exhausted partway through a suffix, since the rest of each
    matching sentence's text is unknown to the query.
- **`build_trie_from_zip(zip_path=DEFAULT_ARCHIVE_PATH) -> Trie`** — full build from scratch.
- **`load_or_build_trie()`** — convenience: loads a cached `corpus_index.pickle` if present,
  otherwise builds and caches it. Recommended for the CLI (Member 3) so the corpus isn't
  rebuilt on every run.

## Design decisions already made (do not silently change without telling teammates)

1. **Corpus location**: `Archive.zip` is expected at the repository root
   (`init_offline.build_index.DEFAULT_ARCHIVE_PATH`). No env var/config file — pass an explicit
   path to `build_trie_from_zip()` if you need a different location.
2. **Normalization ownership**: happens here, at trie-build time, via `normalize()`. Member 2
   must reuse this exact function for query normalization — do not re-implement it.
3. **Matching granularity**: the trie supports substrings starting at **word boundaries only**
   (matching the worked examples in `PROJECT_SPEC.md` §6.3, which all start on a full word).
   Typo tolerance (character-level) happens during Member 2's traversal of `TrieNode.children`,
   not inside this module.
4. **Empty lines**: skipped, not stored.
5. **Duplicates**: not de-duplicated — every occurrence keeps its own `SentenceRef`.
6. **Decoding**: UTF-8 first, falls back to latin-1 (never raises) for any corpus file with
   non-UTF-8 bytes.

## Known cost / open item

Building the trie inserts one path per word in every corpus line (needed to support
substring-anywhere matching), so build time scales with total words × average remaining-line
length, not just total characters. On the full ~122MB corpus this takes several minutes (see
`tests/test_init_offline/test_integration_real_corpus.py::test_full_trie_build_is_queryable`,
gated behind `RUN_SLOW_TESTS=1` because of this). `load_or_build_trie()`'s pickle cache avoids
paying this cost more than once. If build time becomes a blocker, revisit with the team before
optimizing further (e.g. capping indexed word-starts per very long line) — not done here since
the brief sets no hard performance bound.

## Running the tests

```bash
python -m pytest tests/test_init_offline/            # fast unit tests + light integration checks
RUN_SLOW_TESTS=1 python -m pytest tests/test_init_offline/test_integration_real_corpus.py  # + full build
```
