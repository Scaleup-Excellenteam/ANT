# SPEC — Member 1: Init / Offline Builder (Owner: You)

> Derived entirely from `PROJECT_SPEC.md`. This is your personal build spec for the **offline
> phase** of the Auto-Complete project. Read `PROJECT_SPEC.md` first for full project context.

## Role & Goal

You own the **offline/init phase**: reading the entire text corpus (`Archive.zip`, 1,518 files,
nested folders) and turning it into a search-ready structure that Yazan's matching function can
query quickly. Nothing in the online phase can run until your output exists. Your work is judged
indirectly through the project's two grading metrics — **correctness** and **efficiency** — since
a badly organized structure makes Yazan's typo-tolerant search slow or wrong.

You may write this phase in **any language** (per the brief) — but whatever you choose must be
easy for Yazan to consume from **Python** (their function is required to be Python).

## Inputs You Receive / Outputs You Must Produce

**Input:** the raw corpus — `Archive.zip`, containing English `.txt` files at arbitrary folder
depth (verified: some files sit at the root, others are nested 2+ levels deep, e.g.
`python-3.8.4-docs-text/c-api/abstract.txt`).

**Output (your contract with Yazan):** a prepared, documented structure that supports, at minimum:
- Fast lookup by prefix/substring of a query string.
- For every stored unit, retrieval of: the **full original line** (with punctuation, as-is),
  the **source file path**, and the **line offset** within that file.

You decide the concrete shape (in-memory object, or an object plus a serialized file on disk) —
but you must **write it down precisely** (data structure, field names, access functions) before
handing off, since Yazan's search code depends on it exactly.

## Detailed Requirements (from `PROJECT_SPEC.md`)

- **§4 (Corpus):** a "sentence" = one full line in a file, not grammatically split. You must
  preserve each line's original text unmodified (for output later) while also being able to
  produce a normalized version for matching (see below — normalization itself is arguably shared
  with Yazan, but you must decide whether normalization happens at load time or at query time).
- **§4:** corpus location is "known in advance" — no config mechanism is specified anywhere in the
  brief. **You must decide and document** how the program finds the corpus (e.g., hardcoded path,
  relative path convention, or expects it already extracted to a folder alongside the code).
- **§3 (Architecture):** the offline phase must fully finish before the online phase starts serving
  queries — build once, serve many times.
- **§13 (Dependencies):** cross-language handoff is explicitly allowed by the brief — if you build
  in a non-Python language, you must produce a file format Yazan's Python code can read (e.g. a
  serialized/pickled structure, JSON, or a custom binary/text format you document clearly).
- **§14 (Edge cases, your responsibility):**
  - Empty lines in corpus files — decide whether to skip or store as empty sentences (document
    the choice).
  - Extremely long lines, non-prose content (code blocks, tables) inside `.txt` files — the brief
    doesn't address this; decide how to handle and document it.
  - Files that fail to decode as text — decide a fallback (skip + log, error out, etc.).
  - Duplicate sentences across multiple files — brief doesn't forbid or require de-duplication;
    default to keeping all occurrences (each with its own source+offset) unless you and Yazan
    agree otherwise, since correctness ("get the right top-5") likely depends on treating repeated
    matches as independent candidates.

## Concrete Task Checklist

1. Decide corpus access convention (path to `Archive.zip` or its extracted folder) — document it
   at the top of your module/README.
2. Write the recursive folder-tree walker to enumerate every `.txt` file at any depth.
3. For each file, read it line by line; for each non-skipped line, record: full original text,
   source file path (relative, so output paths are portable), and 1-based (or 0-based — document
   which) line offset.
4. Choose and implement your search-friendly structure (e.g., a prefix tree/trie over words, an
   inverted index, or another structure of your choice) that lets Yazan look up "all sentences
   whose normalized text could plausibly contain the query as a substring" efficiently — the
   efficiency of this step directly affects the "efficiency" grading metric.
5. Decide whether input normalization (lowercase, strip punctuation, collapse repeated spaces —
   required for matching per `PROJECT_SPEC.md` §5.4) is applied to your stored data at build time,
   or left for Yazan to apply at query time. **Whichever you choose, document it explicitly** —
   this is a shared contract detail that must not be assumed silently by either side.
6. Expose a clean access API/function(s) for Yazan to call (e.g., "get candidate sentences given a
   normalized prefix/word") — write the exact function signature(s) and return types down.
7. (Optional, not required by brief but worth considering for efficiency) implement caching/
   serialization of the built structure to disk so repeated runs don't re-parse 122MB of text
   every time.
8. Write a short internal test/sanity check: load the real corpus, confirm file count and total
   line count are sane, confirm nested folders were traversed (spot-check a deeply nested file
   like `python-3.8.4-docs-text/c-api/abstract.txt` is present in your structure).
9. Write down your final structure's shape and access API in a short document/README section so
   Yazan and Mohammad can integrate without asking you for verbal explanations every time.

## Acceptance Criteria (self-check before handing off)

- Given a known test file with known lines, your structure returns the correct source path and
  offset for a line you look up directly.
- Full corpus load completes without crashing and without silently dropping whole files.
- You can explain, in your own words, why your chosen structure is efficient for prefix/substring
  lookup (you will need to justify this — the brief requires the team to understand and defend
  their design choices, not just produce output).
- Yazan can call your access function(s) and get results without needing to read your internal
  implementation.

## Open Questions You Must Resolve

- Corpus path/location convention (no default given by the brief).
- Where normalization happens (load-time vs. query-time) — **communicate your decision to Yazan
  explicitly**, it changes what their matching code expects to receive.
- Handling of empty lines, non-English/non-prose lines, decode failures, and duplicate sentences.
- Whether to persist a prebuilt index to disk (perf optimization, your call).

## Dependencies / Hand-off Notes

- **You depend on:** nothing — you are the first stage.
- **Yazan depends on you for:** the search structure + access API + the normalization contract.
- **You must hand off before Yazan can finish:** a stable, documented structure/API. If you change
  its shape later, you must notify Yazan immediately since their matching code is built directly
  against it.
- **Mohammad depends on you indirectly** (through Yazan) for overall system correctness/perf, and
  will need to know your corpus-path convention to run the whole pipeline end-to-end for testing.
