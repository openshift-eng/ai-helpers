import re
from pathlib import Path


ROOT = Path(__file__).parent.parent
VERSION_PATTERN = r"([0-9]+\.[0-9]+\.[0-9]+)"


def action_pin(workflow, action):
    content = (ROOT / workflow).read_text()
    matches = re.findall(
        rf"^[ \t]*uses:[ \t]+{re.escape(action)}@([0-9a-f]{{40}})[ \t]+# v{VERSION_PATTERN}$",
        content,
        re.MULTILINE,
    )
    assert len(matches) == 1, f"expected one full-SHA {action} pin with a version comment"
    return matches[0]


def test_skillsaw_versions_are_synchronized():
    requirements = (ROOT / "requirements-dev.txt").read_text()
    python_versions = re.findall(rf"^skillsaw=={VERSION_PATTERN}$", requirements, re.MULTILINE)
    assert len(python_versions) == 1, "expected exactly one skillsaw==X.Y.Z requirement"

    lint_pin = action_pin(".github/workflows/lint-plugins.yml", "stbenjam/skillsaw")
    review_pin = action_pin(".github/workflows/lint-review.yml", "stbenjam/skillsaw/review")

    assert lint_pin == review_pin, "skillsaw lint and review action pins differ"
    assert lint_pin[1] == python_versions[0], "skillsaw action and Python versions differ"
