# SPEC — Member 2: Matching + Scoring Engineer (Owner: Yazan)

> Derived entirely from `PROJECT_SPEC.md`. This is Yazan's personal build spec for the
> **typo-tolerant matching and scoring core** of the Auto-Complete project. Read
> `PROJECT_SPEC.md` first for full project context.

## Role & Goal

You own the **core algorithm**: given a user's typed prefix and the search structure built by
the Init teammate, find every corpus sentence that "matches" (per the exact definition below),
score each match, and return the best 5 as `AutoCompleteData` objects. This is the most precisely
specified — and most heavily graded — part of the project ("correctness" in `PROJECT_SPEC.md` §8
is almost entirely about this piece).

This function **must be written in Python** — this is a hard requirement from the brief, unlike
the Init phase which is language-flexible.

## Inputs You Receive / Outputs You Must Produce

**Input:** whatever structure/API the Init teammate hands off (see `SPEC_MEMBER_1_INIT.md`) —
confirm with them exactly: (a) the access function signature(s) you call, (b) whether text is
pre-normalized or you must normalize it yourself, (c) what fields you get back (original text,
source path, offset).

**Output (your contract with Mohammad):**
```python
@dataclass
class AutoCompleteData:
    completed_sentence: str   # ORIGINAL text, punctuation intact — not the normalized form
    source_text: str          # source file path
    offset: int               # line offset in that file
    score: int                # per the scoring rule below
    # you may add your own methods as needed (brief explicitly allows this)

def get_best_k_completions(prefix: str) -> List[AutoCompleteData]:
    ...
```
This function must return **exactly the top 5** matches (or fewer if fewer valid matches exist —
see Open Questions), sorted by score descending, ties broken alphabetically by
`completed_sentence` (this final sort may also be done by Mohammad in the serving layer — agree
with him on where the tie-break sort actually happens so it isn't done twice or skipped).

## Detailed Requirements (from `PROJECT_SPEC.md` §5–§6)

### Matching definition (§5.3)
The user's (normalized) input matches a candidate sentence if it is a substring of that sentence,
or becomes one after applying **at most one** of:
1. Character substitution
2. Character insertion
3. Character deletion

**More than one edit anywhere ⇒ not a match at all** (excluded, not just low-scored).

### Input normalization (§5.4) — confirm ownership with the Init teammate
- Case-insensitive.
- Punctuation in the *user's input* need not be accurate.
- Any run of spaces in the input is equivalent to a single space.
- **Output must use the original corpus text** (with its real punctuation/casing) — normalization
  is only for matching, never for what gets displayed.

### Scoring formula (§6) — must be implemented exactly
```
score = 2 × (number of matching characters) − (edit penalty)
```
- Matching characters include spaces.
- Exact match (0 edits) → no penalty.
- Positions are 1-based, computed on the normalized query; for insert/delete, use the position
  where the character would be inserted/was removed.

**Substitution penalty by position:**
| Position | 1 | 2 | 3 | 4 | 5+ |
|---|---|---|---|---|---|
| Penalty | 5 | 4 | 3 | 2 | 1 |

**Insertion/deletion penalty by position:**
| Position | 1 | 2 | 3 | 4 | 5+ |
|---|---|---|---|---|---|
| Penalty | 10 | 8 | 6 | 4 | 2 |

### Required worked examples (§6.3) — treat these as your unit tests
For source sentence **"To be or not to be, that is the question."**:

| Query | Expected Score | Reason |
|---|---|---|
| `To be` | 10 | 5 matching chars incl. space: 2×5 |
| `or Not` | 12 | 6 matching chars, case ignored: 2×6 |
| `be, that` | 14 | 7 matching chars after removing comma: 2×7 |
| `2o be` | 3 | substitute pos 1: 2×4 − 5 |
| `to pe` | 6 | substitute pos 4: 2×4 − 2 |
| `or knot` | 8 | delete extra `k` at pos 4: 2×6 − 4 |
| `or nt` | 8 | insert missing `o` at pos 5: 2×5 − 2 |
| `not be` | N/A | not a match — no score, excluded entirely |

A parallel Hebrew example set exists in `google_project_2026_part_a.docx` for the sentence
"להיות או לא להיות, זאת השאלה" — same formula, useful as a second independent check.

## Concrete Task Checklist

1. Agree with the Init teammate on the exact access API and normalization ownership (see above)
   before writing any matching code.
2. Implement input normalization (if it's your responsibility) as a small, independently testable
   function: lowercase, strip/ignore punctuation, collapse whitespace runs.
3. Implement the core "match with ≤1 edit" check between a normalized query and a candidate
   sentence (or candidate substring window) — this is the algorithmic heart of the project. It
   likely needs to be efficient (not brute-force over every full sentence for every query) —
   discuss with Init teammate whether their structure lets you prune search space (e.g. only
   examine sentences/branches sharing a long-enough common prefix with the query).
4. Implement the scoring function separately from the match-detection function, so it can be
   unit-tested in isolation against the table in §6.3 above.
5. Wire scoring + matching together to scan candidates from Init's structure and collect all valid
   matches with their scores.
6. Implement top-5 selection: sort by score descending, tie-break alphabetically by
   `completed_sentence` (confirm with Mohammad whether this sort lives here or in his layer —
   pick one owner, document it).
7. Return `AutoCompleteData` objects using the **original, non-normalized** sentence text, correct
   source path, and correct offset (pulled through from Init's structure).
8. Handle the "fewer than 5 valid matches" case per your team's decision (see Open Questions) —
   document what you chose so Mohammad's CLI layer can handle it correctly.
9. Write unit tests for the scoring table (§6.3) **before** integrating with real corpus data —
   this is explicitly called out in `PROJECT_SPEC.md` §10 as the recommended test-first target.

## Acceptance Criteria

- All 8 rows of the "To be or not to be..." table produce exactly the documented score (or `N/A`
  correctly excluded) from your implementation.
- A query with 2+ required edits against every candidate returns no match for that candidate
  (verify it's excluded, not scored 0 or negative and kept).
- Given real corpus data, querying a known short phrase you inserted/verified manually returns
  correct source file + offset.
- You can explain your algorithm's time complexity and why it's not brute-force over the entire
  corpus per keystroke (efficiency metric, §8).

## Open Questions You Must Resolve (with input from teammates)

- What happens when fewer than 5 valid matches exist? (Brief doesn't say — decide: return fewer,
  and make sure Mohammad's display code handles a shorter list gracefully.)
- Exactly where the final alphabetical tie-break sort is implemented (you vs. Mohammad) — pick one
  owner.
- Whether normalization happens in your code or Init's — must match what was documented in
  `SPEC_MEMBER_1_INIT.md`.

## Dependencies / Hand-off Notes

- **You depend on:** the Init teammate's finished, documented search structure and access API.
- **Mohammad depends on you for:** the `get_best_k_completions` function and the
  `AutoCompleteData` contract exactly as specified above — do not change the field names/types
  without telling him, since his CLI/output code and test suite are built against this exact
  shape.
- **You must hand off:** the working `get_best_k_completions` function, its test suite (proving
  the scoring table passes), and a short note on where you landed on the open questions above.
