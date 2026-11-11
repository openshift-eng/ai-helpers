"""Read and write the JSON files the disruption skills share.

The investigation state (`investigation.json`) and the files it references
are read by other skills, so every write goes to a unique temporary file in
the same directory and is swapped in with os.replace. A reader never sees a
partial file, and concurrent writers do not collide on the temporary name.
"""
import json
import os
import sys
import tempfile


class StateError(RuntimeError):
    """An existing state file could not be read, so it was left untouched."""


def write_json_atomic(path, data, indent=None):
    """Write `data` as JSON to `path` without ever exposing a partial file."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=indent)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError as cleanup_error:
            print("Warning: could not remove temporary file %s: %s" % (tmp, cleanup_error), file=sys.stderr)
        raise


def load_state(path):
    """Return the state dict at `path`, or {} when the file does not exist yet.

    Raises StateError when the file exists but is unreadable or not a JSON
    object, so a caller never replaces another skill's results with its own.
    """
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            state = json.load(f)
    except (OSError, ValueError) as e:
        raise StateError("cannot read state file %s (%s); it was not overwritten. Fix or move it, "
                         "or pass a different --state-file." % (path, e)) from e
    if not isinstance(state, dict):
        raise StateError("state file %s is not a JSON object; it was not overwritten. Fix or move it, "
                         "or pass a different --state-file." % path)
    return state
