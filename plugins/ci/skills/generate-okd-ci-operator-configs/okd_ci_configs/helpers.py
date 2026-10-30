"""Git URL mapping, variable substitution, and CI image coordinates."""

from typing import NamedTuple, Optional, Tuple


class ImageCoordinate(NamedTuple):
    """Represents a registry.ci.openshift.org/namespace/name:tag coordinate."""
    namespace: str
    name: str
    tag: str

    def unique_key(self) -> str:
        return f'{self.namespace}_{self.name}_{self.tag}'

    def as_dict(self) -> dict:
        return {
            'namespace': self.namespace,
            'name': self.name,
            'tag': self.tag,
        }


# ---------------------------------------------------------------------------
# Pure-Python helpers (replicate artcommonlib utilities)
# ---------------------------------------------------------------------------

def _remove_prefix(s: str, prefix: str) -> str:
    if s.startswith(prefix):
        return s[len(prefix):]
    return s


def _remove_prefixes(s: str, *prefixes: str) -> str:
    for p in prefixes:
        s = _remove_prefix(s, p)
    return s


def _remove_suffix(s: str, suffix: str) -> str:
    if suffix and s.endswith(suffix):
        return s[:-len(suffix)]
    return s


def convert_remote_git_to_https(source_url: str) -> str:
    """Normalize any git remote URL to ``https://host/org/repo``."""
    url = source_url.strip().rstrip('/')
    url = _remove_prefixes(url, 'http://', 'https://', 'git://', 'git@', 'ssh://')
    url = _remove_suffix(url, '.git')
    url = url.split('@', 1)[-1]  # strip username@

    if ':' in url:
        server, org_repo = url.rsplit(':', 1)
    elif '/' in url:
        server, org_repo = url.rsplit('/', 1)
    else:
        return f'https://{url}'

    return f'https://{server}/{org_repo}'


def split_git_url(url: str) -> Tuple[str, str, str]:
    """Return ``(host, org, repo)`` from any git URL."""
    https = convert_remote_git_to_https(url)
    rest = https[len('https://'):]
    server, remainder = rest.split('/', 1)
    org, repo_name = remainder.split('/', 1)
    return server, org, repo_name


def deep_get(d, *keys, default=None):
    """Safely navigate nested dicts."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key)
            if d is None:
                return default
        else:
            return default
    return d if d is not None else default


def substitute_vars(value: str, variables: dict) -> str:
    """Replace ``{VAR}`` placeholders in *value* using *variables*."""
    if not isinstance(value, str):
        return value
    for k, v in variables.items():
        value = value.replace('{' + k + '}', str(v))
    return value


def deep_substitute(obj, variables: dict):
    """Recursively substitute {VAR} placeholders in a nested data structure."""
    if isinstance(obj, str):
        return substitute_vars(obj, variables)
    if isinstance(obj, dict):
        return {k: deep_substitute(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_substitute(item, variables) for item in obj]
    return obj


def get_public_upstream(remote_git: str, public_upstreams: list) -> Tuple[str, Optional[str], bool]:
    """
    Map a private git URL to its public equivalent using the group.yml
    ``public_upstreams`` list.

    Uses longest-match semantics to match the original
    ``SourceResolver.get_public_upstream``.

    Returns ``(url, public_branch_or_None, has_public_upstream)``.
    """
    remote_https = convert_remote_git_to_https(remote_git)

    if public_upstreams:
        target_priv_prefix: Optional[str] = None
        target_pub_prefix: Optional[str] = None
        target_pub_branch: Optional[str] = None

        for mapping in public_upstreams:
            priv = mapping['private']
            pub = mapping['public']
            https_priv = convert_remote_git_to_https(priv)
            https_pub = convert_remote_git_to_https(pub)

            if remote_https.startswith(f'{https_priv}/') or remote_https == https_priv:
                # Prefer the longest matching prefix
                if target_priv_prefix is None or len(https_priv) > len(target_priv_prefix):
                    target_priv_prefix = https_priv
                    target_pub_prefix = https_pub
                    target_pub_branch = mapping.get('public_branch')

        if target_priv_prefix and target_pub_prefix:
            return (
                f'{target_pub_prefix}{remote_https[len(target_priv_prefix):]}',
                target_pub_branch,
                True,
            )

    return remote_https, None, False


def convert_to_imagestream_coordinate(pullspec: str) -> ImageCoordinate:
    """Split ``registry.ci.openshift.org/ns/is:tag`` into an ``ImageCoordinate``."""
    if not pullspec.startswith('registry.ci.openshift.org/'):
        raise ValueError(
            f'OKD images must be sourced from registry.ci.openshift.org; cannot use {pullspec}'
        )
    parts = pullspec.split('/')
    namespace = parts[1]
    name_tag = parts[2]
    name, tag = name_tag.split(':', 1)
    return ImageCoordinate(namespace=namespace, name=name, tag=tag)
