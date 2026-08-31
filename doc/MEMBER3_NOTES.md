# Member 3 - Initial Integration Notes

## Own these files

- `src/cli.py`
- `src/main.py` (serving/integration entry point)
- `tests/test_cli.py`

`src/mock_matching.py` is temporary development scaffolding and should be
removed or stopped being imported once Member 2 provides the real matcher.

## Do not reimplement partner logic here

Member 1 owns corpus loading/index creation.
Member 2 owns typo-tolerant matching and scoring.
Member 3 owns interaction, output, integration behavior, and end-to-end tests.

## Final integration checklist

1. Member 1 init/load completes before serving starts.
2. Member 2 exposes `get_best_k_completions(prefix)`.
3. Results are `AutoCompleteData(completed_sentence, source_text, offset, score)`.
4. Verify score-descending + alphabetical tie behavior with Member 2.
5. Replace mock matcher import.
6. Add real-corpus integration tests.
7. Manually verify source path and offset against the corpus.
8. Measure response time with the real corpus.
