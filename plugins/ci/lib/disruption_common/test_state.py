"""Tests for disruption_common.state — atomic JSON writes and safe state loading."""
import json
import os
import sys

import pytest

# Run as a script (make test), the package parent is not on sys.path yet.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disruption_common.state import StateError, load_state, write_json_atomic  # noqa: E402


def test_write_json_atomic_creates_directories_and_leaves_no_temp(tmp_path):
    path = tmp_path / "a" / "b" / "state.json"
    write_json_atomic(str(path), {"x": 1})
    write_json_atomic(str(path), {"x": 2}, indent=2)
    assert json.loads(path.read_text()) == {"x": 2}
    assert os.listdir(path.parent) == ["state.json"]


def test_write_json_atomic_keeps_the_old_file_when_dump_fails(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"keep": true}')
    with pytest.raises(TypeError):
        write_json_atomic(str(path), {"bad": object()})
    assert json.loads(path.read_text()) == {"keep": True}
    assert os.listdir(tmp_path) == ["state.json"]


def test_load_state(tmp_path):
    assert load_state(str(tmp_path / "missing.json")) == {}
    good = tmp_path / "good.json"
    good.write_text('{"schema_version": 1}')
    assert load_state(str(good)) == {"schema_version": 1}
    for name, text in (("corrupt.json", "{nope"), ("list.json", "[1]")):
        bad = tmp_path / name
        bad.write_text(text)
        with pytest.raises(StateError, match="not overwritten"):
            load_state(str(bad))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
