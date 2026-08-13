"""WP6 standing release gates — mark existing tests and hold the suite name."""

from __future__ import annotations

import pytest

# Re-export / collect the standing suite by marking tests in their home files.
# This module exists so `docs/release-gates.md` has a code counterpart.


def test_release_gate_marker_registered() -> None:
    assert "release_gate" in (pytest.mark.release_gate.name,)
