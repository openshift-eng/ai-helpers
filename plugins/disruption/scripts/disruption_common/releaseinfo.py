"""Component commits from a release payload's releaseinfo (`oc adm release info -o json`).

gather-extra saves it as releaseinfo.json for the payload the cluster ran last. Each
component tag carries the commit it was built from and its source repository.
"""
import re

COMMIT_ANNOTATION = "io.openshift.build.commit.id"
SOURCE_ANNOTATION = "io.openshift.build.source-location"

_GITHUB_RE = re.compile(r"github\.com[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_-][A-Za-z0-9_.-]*?)(?:\.git)?/?$")


def payload_version(info):
    """The release version named by a releaseinfo document, or ''."""
    return ((info.get("metadata") or {}).get("version")
            or (info.get("references", {}).get("metadata") or {}).get("name") or "")


def parse_repo(url):
    """(owner, repo) from a GitHub source-location URL, or None."""
    match = _GITHUB_RE.search(url or "")
    if not match:
        return None
    return match.group(1), match.group(2)


def component_commits(info):
    """tag name -> {commit, source, repo} from references.spec.tags."""
    result = {}
    for tag in ((info or {}).get("references", {}).get("spec", {}).get("tags") or []):
        annotations = tag.get("annotations") or {}
        commit = annotations.get(COMMIT_ANNOTATION)
        if not commit:
            continue
        source = annotations.get(SOURCE_ANNOTATION, "")
        repo = parse_repo(source)
        result[tag["name"]] = {
            "commit": commit,
            "source": source,
            "repo": "%s/%s" % repo if repo else None,
        }
    return result
