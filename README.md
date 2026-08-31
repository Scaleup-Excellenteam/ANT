# AutoComplete Search System - Member 3 Initial Workspace

This workspace follows the structure of the provided GitHub repository while
preparing Mohammad's **Member 3: CLI / Serving + Testing** part before the other
team members finish their implementations.

## What is ready now

- `src/cli.py` - real Member 3 serving logic.
- `src/mock_matching.py` - temporary replacement for Member 2's matching function.
- `src/main.py` - runnable entry point using the mock matcher.
- `tests/test_cli.py` - tests for Member 3 behavior.
- Existing repository helper files are kept under `src/` for structure/context.
- `resources/Archive.zip` contains the provided project corpus, but Member 3's
  current mock mode does not need it yet.

## Run immediately

From the project root:

```bash
python -m src.main
```

You can also run:

```bash
python src/main.py
```

Try:

- `this is` + Enter -> five mock suggestions.
- enter more text -> the previous query is preserved and extended.
- `#` -> reset the query.
- `few` -> mock fewer-than-five behavior.
- `none` -> mock zero-match behavior.
- `~` -> exit (kept from the original repository's CLI convenience behavior).

## Run Member 3 tests

```bash
python -m pytest tests/test_cli.py -q
```

## When Member 2 finishes

In `src/main.py`, replace the mock import:

```python
from .mock_matching import get_best_k_completions
```

with Yazan's real module, for example:

```python
from .matching import get_best_k_completions
```

The required contract is:

```python
def get_best_k_completions(prefix: str) -> List[AutoCompleteData]:
    ...
```

## When Member 1 finishes

Add Member 1's initialization/loading call in `src/main.py` **before**
`run_cli(...)`. Confirm their corpus/index path and offset convention before
integration.

## Team decisions currently used by this initial workspace

- Empty input: print a message and do not search.
- Fewer than 5 matches: display only the valid matches.
- Zero matches: print `No suggestions found.`.
- Equal score: alphabetical order by completed sentence.
- `#`: reset the accumulated query.
- Query stays accumulated after every search so the user can continue typing.

## Important note

The original GitHub `auto_complete_data.py` currently contains a malformed
`offֵset` field spelling. This workspace uses the required `offset` field from
the assignment/spec contract so the Member 3 code can integrate cleanly later.
