"""Tests for disruption_common.state — atomic JSON writes and safe state loading."""
import json
import os
import sys
import threading
from unittest.mock import patch

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


def test_write_json_atomic_logs_a_temp_file_it_cannot_remove(tmp_path, capsys):
    path = tmp_path / "state.json"
    with patch("os.unlink", side_effect=PermissionError("denied")):
        with pytest.raises(TypeError):
            write_json_atomic(str(path), {"bad": object()})
    assert "could not remove temporary file" in capsys.readouterr().err
    assert not path.exists()


def test_concurrent_writers_never_leave_a_partial_file(tmp_path):
    path = tmp_path / "state.json"
    payloads = [{"writer": n, "rows": list(range(2000))} for n in range(8)]
    errors = []

    def write(payload):
        try:
            for _ in range(10):
                write_json_atomic(str(path), payload)
        except Exception as e:  # noqa: BLE001 - reported through the assertion below
            errors.append(e)

    threads = [threading.Thread(target=write, args=(payload,)) for payload in payloads]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert json.loads(path.read_text()) in payloads
    assert os.listdir(tmp_path) == ["state.json"]


def test_load_state_returns_empty_for_a_missing_file(tmp_path):
    assert load_state(str(tmp_path / "missing.json")) == {}


def test_load_state_returns_the_saved_object(tmp_path):
    good = tmp_path / "good.json"
    good.write_text('{"schema_version": 1}')
    assert load_state(str(good)) == {"schema_version": 1}


@pytest.mark.parametrize("text", ["{nope", "[1]"])
def test_load_state_refuses_a_corrupt_or_non_object_file(tmp_path, text):
    bad = tmp_path / "investigation.json"
    bad.write_text(text)
    with pytest.raises(StateError, match="not overwritten"):
        load_state(str(bad))
    assert bad.read_text() == text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
