"""Small character trie over the DISTINCT WORD VOCABULARY only (tens of thousands of entries,
not millions of corpus lines/suffixes) -- this is the one place a trie is still the right tool
for this project, per the design review that preceded this implementation.

Purpose: let Member 2 fuzzy-match a query's anchor word against real corpus vocabulary (e.g.
the query contains "pyhton" -- is there a vocabulary word within 1 edit of that? yes, "python")
without ever touching the corpus itself. Once a real vocabulary word is found this way, Member 2
looks it up in `word_index.WordInvertedIndex` to get actual candidate sentences.

This is intentionally NOT the corpus-wide suffix trie the original design used -- it only ever
holds the vocabulary (bounded, small), so build cost and memory are both tiny compared to the
corpus itself.
"""

from typing import Dict, Iterable, List, Set


class _TrieNode:
    __slots__ = ("children", "is_end")

    def __init__(self) -> None:
        self.children: Dict[str, "_TrieNode"] = {}
        self.is_end: bool = False


class VocabularyTrie:
    def __init__(self) -> None:
        self.root = _TrieNode()
        self._words: Set[str] = set()

    def build(self, words: Iterable[str]) -> None:
        for word in words:
            self._insert(word)

    def _insert(self, word: str) -> None:
        self._words.add(word)
        node = self.root
        for char in word:
            child = node.children.get(char)
            if child is None:
                child = _TrieNode()
                node.children[char] = child
            node = child
        node.is_end = True

    def contains(self, word: str) -> bool:
        return word in self._words

    def words_containing_substring(self, substring: str) -> List[str]:
        """Every vocabulary word that contains `substring` anywhere (start, middle, or end).

        Used for the short-query fallback (README: query lengths 1-5) and for catching a
        mid-word substring match whose anchor word can't be found via the word index alone.
        Implemented as a flat scan rather than trie traversal -- the trie doesn't accelerate
        "contains anywhere", and the vocabulary is small enough (tens of thousands of entries)
        that a flat scan is simple, fast, and easy for Member 2 to trust.
        """
        if not substring:
            return list(self._words)
        return [word for word in self._words if substring in word]

    def fuzzy_lookup(self, word: str, max_edits: int = 1) -> List[str]:
        """Every vocabulary word within `max_edits` edits (substitution/insertion/deletion,
        per PROJECT_SPEC.md section 5.3's definition of a "correction") of `word`.

        Includes an exact match (0 edits) if present. DFS over the trie with an edit budget,
        so cost scales with the trie's branching near `word`, not with vocabulary size.
        """
        results: Set[str] = set()
        self._dfs(self.root, word, 0, max_edits, "", results)
        return sorted(results)

    def _dfs(
        self,
        node: _TrieNode,
        target: str,
        i: int,
        edits_left: int,
        path: str,
        results: Set[str],
    ) -> None:
        if i == len(target) and node.is_end:
            results.add(path)

        if i < len(target):
            exact_child = node.children.get(target[i])
            if exact_child is not None:
                self._dfs(exact_child, target, i + 1, edits_left, path + target[i], results)

            if edits_left > 0:
                # substitution: replace target[i] with any other trie character
                for char, child in node.children.items():
                    if char != target[i]:
                        self._dfs(child, target, i + 1, edits_left - 1, path + char, results)
                # deletion: target has one extra character not present in the vocab word
                self._dfs(node, target, i + 1, edits_left - 1, path, results)

        if edits_left > 0:
            # insertion: the vocab word has one extra character not present in target
            for char, child in node.children.items():
                self._dfs(child, target, i, edits_left - 1, path + char, results)

    def __len__(self) -> int:
        return len(self._words)

    def __getstate__(self):
        # Serializing the nested nodes can exceed pickle's recursion limit for
        # unusually long corpus tokens. The word set is compact and is enough
        # to reconstruct the trie when loading the cache.
        return {'words': self._words}

    def __setstate__(self, state) -> None:
        self.root = _TrieNode()
        self._words = set()
        self.build(state['words'])
