"""Search structure handed off to the Matching phase (Member 2).

Design (documented per SPEC_MEMBER_1_INIT.md):
    A character-level trie built over every WORD-BOUNDARY SUFFIX of every corpus line.
    For a line "to be or not to be", we insert the suffixes starting at "to be or not to be",
    "be or not to be", "or not to be", "not to be", "to be", "be" -- one insertion per word
    start. This lets the Matching phase find a query as a substring of a sentence starting at
    ANY word boundary (per PROJECT_SPEC.md section 5.3's matching definition), while still
    doing a single character-by-character trie descent per candidate start point.

    Typo tolerance (allowing <=1 substitution/insertion/deletion) and scoring are NOT
    implemented here -- that is Member 2's responsibility. This module only exposes the
    traversal primitives Member 2 needs:
      - `walk_exact(prefix)`: descend along an exact character path (root or any node).
      - `TrieNode.children`: dict[str, TrieNode] for manual/fuzzy descent (substitutions,
        skipping a trie character for a "deletion", or re-trying the same node for an
        "insertion" -- however Member 2 chooses to implement the edit-tolerant DFS).
      - `collect_sentence_refs(node)`: gather every SentenceRef reachable under a node, needed
        once a query is exhausted mid-suffix (the rest of the sentence is unknown to the query,
        so all sentences continuing from that point must be enumerated and scored).

Efficiency note (honest, not overstated): inserting every word-boundary suffix is O(words in
line) insertions per line, each up to O(remaining line length). For a corpus with very long
lines (some real files here have multi-KB lines), this is the dominant cost of the build step.
This trade-off was chosen because the assignment requires substring matches starting anywhere
in the sentence -- a plain prefix-only trie (one insertion per line) cannot support that. If
build time becomes a problem in practice, a cheaper alternative (e.g. capping how many word
starts are indexed per very long line) could be revisited -- flagged here, not implemented,
since the brief does not require a specific performance bound.
"""

from typing import Dict, Iterator, List, Optional

from .models import SentenceRef


class TrieNode:
    __slots__ = ("children", "sentence_refs", "is_end")

    def __init__(self) -> None:
        self.children: Dict[str, "TrieNode"] = {}
        self.sentence_refs: List[SentenceRef] = []
        self.is_end: bool = False


class Trie:
    def __init__(self) -> None:
        self.root = TrieNode()

    def insert_sentence(self, normalized_text: str, ref: SentenceRef) -> None:
        """Insert every word-boundary suffix of `normalized_text`, tagged with `ref`.

        `normalized_text` must already be normalized with `text_utils.normalize()` -- this
        method does not normalize on its own, to keep normalization a single, explicit step
        owned by the caller (see build_index.py).
        """
        if not normalized_text:
            return

        start_positions = self._word_start_positions(normalized_text)
        for start in start_positions:
            self._insert_suffix(normalized_text[start:], ref)

    def walk_exact(self, prefix: str, node: Optional[TrieNode] = None) -> Optional[TrieNode]:
        """Descend from `node` (default: root) along an exact character path.

        Returns None if any character in `prefix` has no matching child. This is the plain
        (no typo tolerance) traversal primitive; Member 2's fuzzy search builds on top of
        `TrieNode.children` directly for the typo-tolerant case.
        """
        current = node or self.root
        for char in prefix:
            next_node = current.children.get(char)
            if next_node is None:
                return None
            current = next_node
        return current

    def collect_sentence_refs(self, node: TrieNode) -> List[SentenceRef]:
        """Gather every SentenceRef reachable at or below `node` (DFS, iterative)."""
        results: List[SentenceRef] = []
        stack = [node]
        while stack:
            current = stack.pop()
            if current.is_end:
                results.extend(current.sentence_refs)
            stack.extend(current.children.values())
        return results

    def _insert_suffix(self, suffix: str, ref: SentenceRef) -> None:
        current = self.root
        for char in suffix:
            child = current.children.get(char)
            if child is None:
                child = TrieNode()
                current.children[char] = child
            current = child
        current.is_end = True
        current.sentence_refs.append(ref)

    @staticmethod
    def _word_start_positions(normalized_text: str) -> Iterator[int]:
        yield 0
        for i in range(1, len(normalized_text)):
            if normalized_text[i - 1] == " " and normalized_text[i] != " ":
                yield i
