"""Download upstream Dockerfiles and parse their FROM instructions."""

import re
import sys
from typing import List, Optional, Tuple

import requests

from .helpers import split_git_url


_FROM_VALUE_RE = re.compile(
    r"""(?xi)
    \s*
    (?P<image>\S+)
    (?:\s+AS\s+(?P<name>\S+))?
    """,
)


def _image_from(from_value: str) -> Tuple[Optional[str], Optional[str]]:
    m = _FROM_VALUE_RE.match(from_value)
    return m.group('image', 'name') if m else (None, None)


def parse_dockerfile_froms(content: str) -> List[Tuple[str, Optional[str]]]:
    """Parse ``FROM`` instructions.  Returns ``[(image, stage_name_or_None), ...]``."""
    results: List[Tuple[str, Optional[str]]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith('FROM '):
            image, stage = _image_from(stripped[5:])
            if image:
                results.append((image, stage))
    return results


# ---------------------------------------------------------------------------
# Downloading files from GitHub
# ---------------------------------------------------------------------------

def download_dockerfile(
    public_url: str,
    branch: str,
    path: str,
    token: Optional[str] = None,
) -> Optional[str]:
    """Download a file from GitHub via raw.githubusercontent.com."""
    _, org, repo = split_git_url(public_url)
    raw_url = f'https://raw.githubusercontent.com/{org}/{repo}/{branch}/{path}'
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'
    try:
        resp = requests.get(raw_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.text
        print(
            f'  WARNING: HTTP {resp.status_code} downloading {raw_url}',
            file=sys.stderr,
        )
        return None
    except Exception as exc:
        print(f'  WARNING: Error downloading {raw_url}: {exc}', file=sys.stderr)
        return None
