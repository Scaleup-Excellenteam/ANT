# PROJECT SPEC — Auto-Complete Sentences (Google Excellence Program, Part A)

> **Status of this document:** This is a **requirements specification**, derived solely from
> `google_project_2026_part_a.docx` (the assignment brief) and the contents of `Archive.zip`
> (the provided corpus). **No source code exists in this repository at the time of writing.**
> Every section describing implementation (architecture decisions, classes, functions, tests,
> config) reflects what the assignment *requires you to build*, not something already built.
> Sections are explicitly marked **[NOT IMPLEMENTED]** where that applies.

---

## 1. Project Overview & Goal

**Name:** "השלמת משפטים אוטומטית" — Automatic Sentence Completion
**Program:** אקסלנטים באקדמיה – פרויקט גוגל (Excellenteam Academy – Google Project)
**Scope of this spec:** Part A (שלב א׳) — functionality only. (The brief references a later stage
for additional requirements not covered here.)

**Goal:** Build a team system (3 people: you, Yazan, Mohammad) that performs **autocomplete /
sentence completion**, similar to a search engine's suggestion box. Given a corpus of English text
files (sentences = full lines in each file) and a string the user is currently typing, the system
must return the **5 best-matching complete sentences** from the corpus, tolerant of at most one
typing mistake.

Stated pedagogical goals (from the brief, not functional requirements):
- Practice the full software development lifecycle: requirements → algorithm/data-structure choice
  → implementation → correctness/efficiency verification.
- Own the code you produce — you must be able to explain and defend any AI-assisted code.
- AI/LLM tools (e.g. Gemini) are explicitly **permitted and encouraged**, provided the team fully
  understands, verifies, and can explain the resulting solution.

---

## 2. Deliverables Required by the Brief

1. An **init/build function** — reads the text corpus and prepares it for fast lookups.
   - Language: **any language of the team's choice.**
2. A **completion function**, written **in Python** (this is a hard requirement, unlike the init step):
   ```python
   get_best_k_completions(prefix: str) -> List[AutoCompleteData]
   ```
3. A **full runnable program** with two operating stages (offline / online — see §5).
4. Implicit deliverable: the team must be able to explain the algorithm and scoring logic in detail
   (verification requirement, not a code artifact).

---

## 3. Architecture (Required Shape — Not Yet Built)

**[NOT IMPLEMENTED]** — no code exists. The brief mandates a two-phase architecture:

```
┌─────────────────────────┐        ┌──────────────────────────────┐
│  OFFLINE / INIT PHASE    │        │  ONLINE / SERVING PHASE       │
│  (language: any)         │        │  (language: Python, required) │
│                          │        │                                │
│  Read corpus from        │──────▶│  Loop:                        │
│  known location          │ prepared│   - read user keystrokes     │
│  (Archive.zip contents)  │  data   │   - on Enter: call            │
│  → build a search        │        │     get_best_k_completions()  │
│    structure             │        │   - print top-5 suggestions   │
└─────────────────────────┘        │   - allow continued typing    │
                                    │   - "#" resets to start state │
                                    └──────────────────────────────┘
```

Key architectural constraints stated in the brief:
- The init step's chosen in-memory/on-disk representation must be designed **for the benefit of**
  the completion function (i.e., data-structure choice is up to the team, but must serve the
  scoring/matching algorithm efficiently).
- The two phases are conceptually separate: build once, then serve repeatedly.
- No specific technology, database, or external service is mandated or mentioned anywhere in the
  brief. **There is no database, API, or network component specified.** This is a local,
  single-process command-line tool as described.

No repository code exists to confirm what data structure (trie, inverted index, suffix array, etc.)
the team will actually choose — that decision has **not yet been made**.

---

## 4. Data / Corpus (`Archive.zip`) — Actual, Verified Contents

This part of the spec **is** based on inspecting the real file, since it is present in the repo.

- `Archive.zip` contains **1,518 files**, total ~121.9 MB uncompressed.
- Files are `.txt`, in **English**, and may include punctuation (`@ ! . , $` etc., per the brief).
- Confirmed nested folder structure exists (not all files sit at the top level), e.g.:
  ```
  Archive.zip
  ├── 0130903086.txt
  ├── abs-guide.txt
  ├── Art Of Intel x86 Assembly.txt
  ├── postgresql-11-A4.txt
  ├── python-3.8.4-docs-text/
  │   ├── about.txt
  │   ├── bugs.txt
  │   └── c-api/
  │       ├── abstract.txt
  │       ├── allocation.txt
  │       └── ... (many more)
  ├── Tutorials.txt
  ├── user-handbook.txt
  └── userguide.txt
  ```
  This matches the brief's statement: *"the text files are stored in a folder tree... a text file
  can be inside a folder, inside a folder inside a folder, etc."*
- **Per the brief, a "sentence" = one full line inside a file** (not sentence-boundary punctuation
  detection). This is an explicit simplifying definition the team must follow.
- The brief says the corpus location is "known in advance" to the offline step — no configuration
  mechanism (env var, config file, CLI arg) for the corpus path is specified. **[OPEN QUESTION]**
  the team must decide how the program locates `Archive.zip` / its extracted contents.

---

## 5. Functional Requirements

### 5.1 Required data class

The brief supplies this exact signature (fields only; methods are left to the team):

```python
@dataclass
class AutoCompleteData:
    completed_sentence: str   # the full matched sentence, original casing/punctuation
    source_text: str          # which source file it came from (path)
    offset: int                # line/offset within that source file
    score: int                 # match score (see §6)
    # methods that you need to define by yourself
```

**[NOT IMPLEMENTED]** — no methods are specified beyond the fields above; the brief explicitly
leaves method design to the team ("methods that you need to define by yourself").

### 5.2 Required function signature

```python
get_best_k_completions(prefix: str) -> List[AutoCompleteData]
```
- `k` is fixed at 5 by the brief ("the five best completions"), despite the generic `k` naming.
- Must be callable repeatedly per keystroke-batch (see §7, online loop).

### 5.3 Matching definition

A user-typed string **matches** a candidate sentence if it is a substring of that sentence, or
becomes a substring after applying **at most one "fix"**. A "fix" is exactly one of:
1. **Character substitution**
2. **Character insertion**
3. **Character deletion**

More than one edit anywhere in the candidate ⇒ **not a match**, no score is produced for that
candidate at all (it is excluded, not scored low).

### 5.4 Input normalization requirements

- Case-insensitive comparison (uppercase/lowercase in user input must not matter).
- Punctuation typed by the user is not required to be accurate/present.
- Any number of spaces between words in the user's input must be treated as equivalent to a single
  space — e.g. `"to be zat,"`, `"to be, zat"`, and `"to be        zat"` must all be scored
  identically against the source sentence.
- **Output must preserve original formatting**: the returned sentence is the literal corpus line,
  including its original punctuation — normalization is only for the *matching* step, not the
  output.

---

## 6. Scoring Specification (Exact Rule From Brief)

```
score = 2 × (number of matching characters) − (edit penalty)
```

- Matching characters include spaces.
- An exact match (0 edits) has **no penalty**.
- At most **one** edit total is allowed per candidate; if none of the three edit types make it fit,
  the candidate is discarded (no score).
- Character positions are **1-based**, computed on the *normalized* query (lowercased, punctuation
  stripped, repeated spaces collapsed). For an inserted/missing character, use the position at which
  it would be inserted.

### 6.1 Substitution penalty (by position of the substituted character)

| Position | 1 | 2 | 3 | 4 | 5+ |
|---|---|---|---|---|---|
| Penalty | 5 | 4 | 3 | 2 | 1 |

### 6.2 Insertion / deletion penalty (by position of the inserted/deleted character)

| Position | 1 | 2 | 3 | 4 | 5+ |
|---|---|---|---|---|---|
| Penalty | 10 | 8 | 6 | 4 | 2 |

### 6.3 Worked examples from the brief (must be used as acceptance tests — see §10)

For the source sentence **"To be or not to be, that is the question."**:

| Query | Score | Reason |
|---|---|---|
| `To be` | 10 | 5 matching chars (incl. space): 2×5 = 10 |
| `or Not` | 12 | 6 matching chars, case ignored: 2×6 = 12 |
| `be, that` | 14 | 7 matching chars after removing comma: 2×7 = 14 |
| `2o be` | 3 | substitute `2`→`t` at position 1; 4 chars match: 2×4 − 5 = 3 |
| `to pe` | 6 | substitute `p`→`b` at position 4; 4 chars match: 2×4 − 2 = 6 |
| `or knot` | 8 | delete extra `k` at position 4 → "or not": 2×6 − 4 = 8 |
| `or nt` | 8 | insert missing `o` at position 5 → "or not": 2×5 − 2 = 8 (inserted char earns no points) |
| `not be` | N/A | not a match: no substring reachable with ≤1 edit; no score assigned |

A parallel Hebrew-language example set for the sentence **"להיות או לא להיות, זאת השאלה"**
(same rule, sanity-checked against the same formula) also appears in the brief and is consistent
with the table above.

---

## 7. Online / Serving Behavior (CLI Loop)

- On startup, offline/init phase must already have completed (corpus loaded/prepared).
- The program then enters an interactive loop:
  1. User types characters.
  2. On **Enter**, the system calls the completion logic and displays the **top 5** suggestions.
  3. Ties (equal score) are broken by **alphabetical order** of the completed sentence.
  4. After suggestions are shown, the user may **continue typing from where they stopped** (the
     query is not necessarily reset after each Enter).
  5. Typing **`#`** signals "done with this sentence" — the system must reset to its initial input
     state (start a fresh query).
- **Output format requirement:** each result must show the original corpus line (with punctuation),
  plus its source file and offset. A sample output shape given in the brief:
  ```
  The system is ready. Enter your text:
  this is
  Here are 5 suggestions:
  1. Alpha: this is a demo. (example.txt:1, score=14)
  2. Beta: this is a demo. (example.txt:2, score=14)
  3. Delta: this is a demo. (example.txt:3, score=14)
  4. Gamma: this is a demo. (example.txt:4, score=14)
  5. Omega: this is a demo. (example.txt:5, score=14)
  this is
  ```
  This is described as "a possible output" (אפשרי) — exact formatting is **not rigidly mandated**,
  but the *content* (rank, sentence, source, offset, score) is expected. **[OPEN QUESTION]** the
  exact print format is left to the team as long as required content is present.

---

## 8. Non-Functional Requirements / Evaluation Metrics

The brief states the solution is graded on exactly two metrics:

1. **Correctness** — does the user get the truly correct top-scoring completions?
2. **Efficiency** — how fast the system returns completions after input.

No numeric performance target (e.g. "under X ms") is given in the brief. **[OPEN QUESTION]** the
team should assume "as fast as reasonably possible" and be ready to justify algorithmic complexity
choices, since the brief's own reference concepts (in the earlier-reviewed, unrelated third-party
repo) discuss O(n log n) style targets — but that is not a requirement stated in *this* brief.

---

## 9. Configuration & Environment

**[NOT IMPLEMENTED / NOT SPECIFIED]**
- No environment variables, config files, or CLI flags are defined anywhere in the brief.
- No corpus path convention is specified beyond "a known location."
- No language/runtime version is pinned (only that the completion function must be Python; no
  version number given).
- No dependency manifest (`requirements.txt`, `pyproject.toml`, etc.) exists yet in this repo.

---

## 10. Testing Strategy

**[NOT IMPLEMENTED]** — there are no test files in this repository yet.

What the brief provides that should become the seed of the test suite:
- The full scoring table in §6.3 (both the English "To be or not to be..." examples and the
  parallel Hebrew example set) should be encoded as **unit tests for the scoring function** before
  any corpus-search logic is layered on top.
- The `this is` → 5-suggestion sample in §7 is a candidate **integration/smoke test** shape, though
  it uses placeholder data (`example.txt`, fictitious names) rather than the real corpus.
- No tests exist for: corpus loading, nested-folder traversal, tie-break-by-alphabet ordering, the
  `#` reset behavior, or performance/timing.

---

## 11. Current Implementation Status

| Area | Status |
|---|---|
| Requirements brief | ✅ Present (`google_project_2026_part_a.docx`) |
| Corpus data | ✅ Present (`Archive.zip`, 1,518 files, verified nested structure) |
| Init/offline function | ❌ Not started |
| `AutoCompleteData` class | ❌ Not started |
| `get_best_k_completions()` | ❌ Not started |
| Matching/typo-tolerance algorithm | ❌ Not started |
| Scoring implementation | ❌ Not started |
| CLI / online loop | ❌ Not started |
| Tests | ❌ Not started |
| Config/build tooling (requirements.txt, etc.) | ❌ Not started |
| Repository/version control for the team's own code | ❌ Not confirmed to exist in this workspace |

**In short: this workspace currently contains only the assignment brief and its input data. All
implementation work is greenfield.**

---

## 12. Technical Decisions Already Made (by the brief itself, not by the team)

These are constraints, not choices the team gets to revisit:
- Completion function must be Python.
- Function signature and `AutoCompleteData` field set are fixed.
- Exactly 5 results returned per query.
- At most 1 edit allowed for a match; scoring formula and penalty tables are fixed as given.
- "Sentence" = one line in a source file (not grammatical sentence splitting).
- Case, punctuation, and whitespace-run differences in the *input* must be normalized before
  matching; output must retain original text.

Everything else (init-phase language, chosen data structure/algorithm, corpus loading mechanism,
exact CLI text/formatting, project layout, dependency choices, whether/how to cache a prebuilt
index between runs) is **undecided** and left to the team.

---

## 13. Dependencies Between Parts

- The **online phase depends entirely on the offline phase** having already built and made
  available whatever structure the completion function needs — the brief explicitly frames this as
  build-once-serve-many.
- The **scoring logic is a prerequisite for the search algorithm**: since edit tolerance affects
  which candidates even qualify as matches, the matching/traversal strategy and the scoring
  function are tightly coupled and should likely be designed together (e.g., pruning search paths
  based on partial score/edit budget as you go), though the brief does not mandate an integrated
  design — it only specifies the two required functions' external contracts.
- The **Python-only constraint applies solely to the completion function**; the init phase has no
  such constraint, meaning cross-language handoff (e.g., an offline step in another language
  producing a serialized file that the Python completion phase reads) is explicitly permitted by
  the brief.

---

## 14. Error Handling & Edge Cases (Explicitly Addressed by the Brief)

- Query with **no valid match** (more than 1 edit needed for every candidate): must not be scored;
  presumably excluded from the top-5 output (brief does not specify what happens if fewer than 5
  valid matches exist at all — **[OPEN QUESTION]**: return fewer than 5? pad? not specified).
  - **[OPEN QUESTION]** what happens if fewer than 5 candidates match: brief neither confirms nor
    denies returning fewer than 5 results.
- **Tie-breaking** for equal scores: alphabetical order (explicitly specified).
- **Reset trigger**: `#` character ends the current sentence-typing session and returns to the
  initial state (explicitly specified).
- Whitespace-run and case differences in user input: explicitly must not affect matching or score.
- Corpus text is guaranteed to be English with punctuation — no non-English/encoding edge cases are
  called out by the brief, but real corpus files (verified) do include non-ASCII/documentation
  formatting quirks (e.g. code samples, tables) that are **not addressed by the brief at all** —
  the team should expect messy real-world text despite the brief's simplified "line = sentence"
  assumption. **[OPEN QUESTION]** how to handle corpus lines that are empty, extremely long, or
  contain non-prose content (code blocks, tables) inside the `.txt` files.

Not mentioned anywhere in the brief (edge cases the team must decide on their own):
- Empty input / single-character input.
- Duplicate sentences across multiple files.
- Corpus files that fail to decode as text.

---

## 15. Anything a Developer Must Know Before Starting

1. **Nothing is built yet.** Do not assume any existing module names, file layout, or partial
   implementation — this spec's §11 status table is the ground truth.
2. **Do not confuse this project with `Scaleup-Excellenteam/google-auto-complete-sentences`** — that
   is a different team's finished solution to the same brief, useful only as an outside reference,
   not as this team's codebase or history.
3. The two "hard" constraints to design around from day one are: (a) Python-only for the completion
   function, and (b) the fixed `AutoCompleteData` shape and `get_best_k_completions` signature —
   changing these later would break the graded contract.
4. Scoring correctness (§6) should be locked down and unit-tested **before** building the
   search/traversal algorithm, since it's the most exactly-specified, most easily verified part of
   the brief, and the whole point of the search structure is to serve this scoring function
   efficiently.
5. Several implementation details are intentionally left open by the brief (data structure choice,
   corpus loading convention, exact CLI text, init-phase language) — the team must make and document
   these decisions themselves; they are not hidden requirements to "discover."
