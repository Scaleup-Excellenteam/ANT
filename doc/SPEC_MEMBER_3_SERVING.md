# SPEC — Member 3: CLI / Serving + Testing Engineer (Owner: Mohammad)

> Derived entirely from `PROJECT_SPEC.md`. This is Mohammad's personal build spec for the
> **interactive serving loop and the overall test suite** of the Auto-Complete project. Read
> `PROJECT_SPEC.md` first for full project context.

## Role & Goal

You own the **online/serving phase**: the interactive command-line program the user actually
types into, and the **test suite** that proves the whole pipeline (Init → Matching → Serving)
works correctly end-to-end. You are the integration point — your code is the first place all
three teammates' work comes together and gets exercised as a real program.

## Inputs You Receive / Outputs You Must Produce

**Input:** the `get_best_k_completions(prefix: str) -> List[AutoCompleteData]` function from
Yazan (see `SPEC_MEMBER_2_MATCHING.md`), which itself depends on the Init teammate's prepared
corpus structure already being loaded/built (see `SPEC_MEMBER_1_INIT.md`).

**Output:** a runnable program that a user launches, types into, and receives live top-5
suggestions from, following the exact interaction rules below — plus a test suite covering all
three layers.

## Detailed Requirements (from `PROJECT_SPEC.md` §7)

- On startup: the offline/init phase must already have completed (corpus loaded) before you enter
  the interactive loop.
- Loop behavior:
  1. User types characters.
  2. On **Enter**, call `get_best_k_completions` with the current typed text and display the
     **top 5** suggestions.
  3. **Ties** (equal score) are broken by **alphabetical order** of `completed_sentence` — confirm
     with Yazan whether this sort already happens in his function or needs to happen in your
     display layer (per his spec's open question — pick one owner between you two).
  4. After suggestions are shown, the user can **continue typing from where they stopped** — the
     query is not necessarily cleared after every Enter.
  5. Typing **`#`** means "done with this sentence" — reset to the initial input state (start a
     fresh query).
- **Output content requirement** (exact formatting is flexible per the brief, but must include):
  rank, the completed sentence (original text/punctuation), its source file, its offset, and its
  score. Sample shape from the brief:
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
  (This is described as "a possible output," not a mandatory exact format — you have latitude on
  presentation as long as the required content is all there.)

## Concrete Task Checklist

1. Confirm with the Init teammate how/when the offline build step is triggered (does your program
   call an init function first, or does it load an already-serialized structure from disk?).
2. Confirm with Yazan the exact `get_best_k_completions` signature and `AutoCompleteData` fields
   you'll be formatting for display (do not assume — read his spec/handoff notes).
3. Build the input loop: read characters as typed, detect Enter (trigger search+display) vs. `#`
   (reset) vs. ongoing typing (accumulate into the current query buffer).
4. Implement the top-5 display formatting (rank, sentence, source, offset, score) — decide your
   own exact text layout, staying consistent with the required content above.
5. Implement/confirm the alphabetical tie-break (wherever it's decided to live between you and
   Yazan) so equal-score results display in a stable, correct order.
6. Handle the "fewer than 5 matches" case gracefully (per whatever Yazan's team decided — display
   however many valid matches exist, don't crash or pad with fake entries).
7. Handle empty/trivial input gracefully (brief doesn't specify — decide sensibly, e.g. show
   nothing or prompt for more input, and document the choice).
8. Write the **test suite** covering:
   - Yazan's scoring table (§6.3) as a regression check at the integration level (not just his
     unit tests — confirm the full pipeline reproduces the same scores end-to-end).
   - The smoke-test shape from §7 (`this is` → 5 suggestions), adapted to real corpus data since
     the brief's example uses placeholder file names.
   - `#` reset behavior: verify typing `#` clears the query state correctly.
   - Alphabetical tie-break: construct/find a case with equal scores and verify ordering.
   - Continued-typing behavior: verify a query can keep accumulating after a suggestion display.
   - Edge cases from `PROJECT_SPEC.md` §14 relevant to serving: empty input, and the
     fewer-than-5-matches case.
9. Do a manual end-to-end run against the real `Archive.zip` corpus once Init and Matching hand
   off their pieces, to confirm real-world performance is acceptable (efficiency metric, §8) and
   that source paths/offsets displayed are correct against actual files.

## Acceptance Criteria

- A full run: start program → type a phrase known to exist in the real corpus → see it in the
  top-5 with correct source file and offset.
- `#` correctly resets the input state mid-session.
- Equal-score results display in alphabetical order.
- Program does not crash on empty input or on a query with zero valid matches.
- Test suite runs and passes against the real corpus (not just mocked data), at least for the
  scenarios listed in the checklist above.

## Open Questions You Must Resolve (with input from teammates)

- Exact print/formatting layout (your call, brief only fixes the required *content*).
- Where the alphabetical tie-break sort is implemented — agree explicitly with Yazan.
- Behavior on empty input (not specified by the brief).
- Behavior when fewer than 5 valid matches exist — must match whatever Yazan's function returns
  in that case (confirm, don't assume).

## Dependencies / Hand-off Notes

- **You depend on:** Init's completed corpus-loading step and Yazan's finished
  `get_best_k_completions` + `AutoCompleteData` contract. You are the **last** stage to build and
  the one who discovers integration mismatches first — flag any contract inconsistency back to
  Init/Yazan immediately rather than silently working around it in your layer.
- **You produce:** the final runnable deliverable and the test suite that validates the other two
  teammates' work, so budget time to actually run against the real 1,518-file corpus, not just
  small hand-written samples.
