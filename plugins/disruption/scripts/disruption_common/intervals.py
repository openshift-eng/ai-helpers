"""Timeline (interval) file loading and backend selection shared by the skills."""
import json
import os

from disruption_common.series import expand_backend_selectors


def backend_matches_filter(backend_name, backend_filter):
    """True when backend_name is one of the exact names backend_filter selects.

    A full connection name matches only itself. A bare base matches only
    `{base}-new-connections` and `{base}-reused-connections`, not localhost,
    http1/http2, service-network, internal-lb, or cache derivatives.
    """
    if not backend_filter:
        return True
    return backend_name in expand_backend_selectors(backend_filter)


def load_items(paths):
    """Load and merge items from one or more timeline JSON files.

    Items are tagged with a _phase ("upgrade" or "conformance") based on file
    ordering.  Timeline files are sorted by filename timestamp — the first is
    the upgrade phase, the second is the conformance/e2e-test phase.
    """
    sorted_paths = sorted(paths, key=lambda p: os.path.basename(p))
    all_items = []
    for idx, path in enumerate(sorted_paths):
        # First file = upgrade, second = conformance
        phase = "upgrade" if idx == 0 and len(sorted_paths) > 1 else "conformance"
        with open(path) as fh:
            data = json.load(fh)
        items = data if isinstance(data, list) else data.get("items", [])
        for item in items:
            item["_phase"] = phase
            item["_source_file"] = path
        all_items.extend(items)
    return all_items
