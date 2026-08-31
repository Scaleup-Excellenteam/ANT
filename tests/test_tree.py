"""Legacy repository test placeholder.

The original repository's tree tests depend on a prebuilt resources/prefix_tree.pkl
and extracted Archive directory. Member 3 does not own that setup, so the active
initial test suite is tests/test_cli.py. Keep this file as a marker for the
existing repository structure until Member 1 finishes the real Init handoff.
"""

import pytest


@pytest.mark.skip(reason="Waiting for Member 1 real corpus/index handoff")
def test_legacy_tree_integration_placeholder():
    pass
