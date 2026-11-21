"""Corrections learned from hand fixes made upstream in openshift/release.

Each rule here exists because a generated config was later fixed by hand in
openshift/release. The PR number that motivated each rule is in its comment.
Rules either apply a fix (recorded in ``REPORT.fixes``) or flag something a
person has to check (recorded in ``REPORT.warnings``). Both lists are printed
at the end of a run.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class FixupReport:

    def __init__(self):
        self.fixes: List[str] = []
        self.warnings: List[str] = []

    def fix(self, msg: str):
        self.fixes.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def print(self):
        if self.fixes:
            print(f'\nApplied {len(self.fixes)} fixes from known upstream corrections:')
            for msg in self.fixes:
                print(f'  FIX: {msg}')
        if self.warnings:
            print(f'\n{len(self.warnings)} items need a manual check:')
            for msg in self.warnings:
                print(f'  CHECK: {msg}')


REPORT = FixupReport()


def parse_version(version: str) -> Tuple[int, int]:
    major, minor = version.split('.')[:2]
    return int(major), int(minor)


# ---------------------------------------------------------------------------
# Images that should not be generated at all
# ---------------------------------------------------------------------------

# openshift/release#87242: UPI is not tested for OKD, so the upi-installer
# image was removed from the OKD installer config.
SKIP_PAYLOAD_TAGS: Dict[str, str] = {
    'upi-installer': 'UPI is not tested for OKD (openshift/release#87242)',
}


# ---------------------------------------------------------------------------
# Base image stream (CentOS Stream 9 vs 10)
# ---------------------------------------------------------------------------

# openshift/release#85990: OKD 5.1 and later build on base-stream10.
FIRST_STREAM10_VERSION = (5, 1)

# openshift/release#84562: assisted-installer-agent needs dhclient, which
# CentOS Stream 10 does not ship, so 5.0 and 5.1 both pin it to the 4.22
# stream9 base. The pin applies from 5.0 onward.
PINNED_PARENTS: Dict[str, Tuple[Tuple[int, int], str]] = {
    'agent-installer-node-agent': (
        (5, 0),
        'registry.ci.openshift.org/origin/scos-4.22:base-stream9',
    ),
}

# Images whose base was hand-edited upstream in ways the generator cannot
# reproduce from ART metadata. Generation proceeds, but a person must compare
# the result with the existing config before replacing it.
HAND_MAINTAINED_PAYLOAD_TAGS: Dict[str, str] = {
    # openshift/release#84562, #86364, #86771
    'haproxy-router-base': 'router base was hand-edited upstream (stream9 pin, '
                           'then a haproxy32 EL9 compat image in #86771)',
    'haproxy-router-haproxy32': 'haproxy32 needs the EL9 compat image from #86771',
    'haproxy-router-haproxy28': 'haproxy28 was pinned to scos-4.22 stream9 in #84562 '
                                'and retired for 5.1+ in #87955',
}


def default_base_stream(okd_version: str) -> int:
    return 10 if parse_version(okd_version) >= FIRST_STREAM10_VERSION else 9


def adjust_parents(
    distgit_key: str,
    payload_tag: str,
    desired_parents: List[str],
    okd_version: str,
    base_stream: int,
) -> List[str]:
    """Apply base-stream policy and per-image pins to the resolved parents."""
    if not desired_parents:
        return desired_parents
    parents = list(desired_parents)

    pin = PINNED_PARENTS.get(payload_tag)
    if pin and parse_version(okd_version) >= pin[0]:
        if parents[-1] != pin[1]:
            REPORT.fix(
                f'{distgit_key}: base {parents[-1]} -> {pin[1]} '
                f'(needs dhclient, missing on CS10; openshift/release#84562)'
            )
            parents[-1] = pin[1]
        return parents

    if base_stream == 10:
        stream9 = f'registry.ci.openshift.org/origin/scos-{okd_version}:base-stream9'
        stream10 = f'registry.ci.openshift.org/origin/scos-{okd_version}:base-stream10'
        # #85990 switched builder stages as well as the final base.
        if stream9 in parents:
            parents = [stream10 if p == stream9 else p for p in parents]
            REPORT.fix(
                f'{distgit_key}: base-stream9 -> base-stream10 '
                f'(OKD {okd_version} builds on CS10; openshift/release#85990)'
            )

    if payload_tag in HAND_MAINTAINED_PAYLOAD_TAGS:
        REPORT.warn(
            f'{distgit_key} ({payload_tag}): {HAND_MAINTAINED_PAYLOAD_TAGS[payload_tag]}. '
            f'Compare with the existing okd-scos config before replacing it.'
        )
    return parents


# ---------------------------------------------------------------------------
# RPM repository injection
# ---------------------------------------------------------------------------

_MIRROR_HOST = re.compile(r'base-(\d+)-(\d+)-(rhel\d+)\.ocp\.svc')
_SERVER_OSE_REPO = re.compile(r'^(rhel-(\d+)-server-ose)(?:-\d+\.\d+)?$')
_REPO_SECTION = re.compile(r'^\[([^\]]+)\]\s*$', re.M)

# Set by the generator when --release-repo is given. normalize_rpm_repo then
# reads the real repo ids from the content mirror's definition files.
MIRROR_SOURCE: Optional['ReleaseRepo'] = None


def _hardcoded_repo_id(base: str, rhel_major: int, okd_version: str) -> str:
    """Fallback without --release-repo: RHEL 10+ ids carry the version (#86112)."""
    return f'{base}-{okd_version}' if rhel_major >= 10 else base


def normalize_rpm_repo(
    distgit_key: str,
    repo_id: str,
    baseurl: str,
    okd_version: str,
) -> Tuple[str, str]:
    """Make the content-mirror host and repo path match the OKD version.

    openshift/release#84562: a 5.0 config pointed at ``base-5-1-rhel10``.
    openshift/release#86112: the mirror serves ``/rhel-10-server-ose-5.1``,
    so the unversioned ``/rhel-10-server-ose`` path returned 404.

    The mirror serves each repo at a path equal to its repo id. With
    --release-repo, the ids come from the mirror's definition file
    (``core-services/release-controller/_repos/ocp-X.Y-rhelN.repo``). Without
    it, RHEL 10 and later get the version suffix and RHEL 9 does not, which
    matches those files as of 2026-11.
    """
    major, minor = parse_version(okd_version)
    version = f'{major}.{minor}'

    def fix_host(match):
        return f'base-{major}-{minor}-{match.group(3)}.ocp.svc'

    new_baseurl = _MIRROR_HOST.sub(fix_host, baseurl)

    new_repo_id = repo_id
    m = _SERVER_OSE_REPO.match(repo_id)
    if m:
        base, rhel_major = m.group(1), int(m.group(2))
        host = _MIRROR_HOST.search(new_baseurl)
        rhel_tag = host.group(3) if host else f'rhel{rhel_major}'
        known_ids = MIRROR_SOURCE.mirror_repo_ids(version, rhel_tag) if MIRROR_SOURCE else None
        if known_ids is None:
            new_repo_id = _hardcoded_repo_id(base, rhel_major, version)
        elif repo_id in known_ids:
            new_repo_id = repo_id
        elif f'{base}-{version}' in known_ids:
            new_repo_id = f'{base}-{version}'
        elif base in known_ids:
            new_repo_id = base
        else:
            REPORT.warn(
                f'{distgit_key}: RPM repo [{repo_id}] is not in the mirror definition '
                f'ocp-{version}-{rhel_tag}.repo, and neither is {base} or '
                f'{base}-{version}. The download URL may return 404'
            )
        if new_repo_id != repo_id:
            new_baseurl = re.sub(
                rf'/{re.escape(repo_id)}(/?)$', rf'/{new_repo_id}\1', new_baseurl,
            )

    if new_baseurl != baseurl or new_repo_id != repo_id:
        REPORT.fix(
            f'{distgit_key}: RPM repo [{repo_id}] {baseurl} -> '
            f'[{new_repo_id}] {new_baseurl} (openshift/release#84562, #86112)'
        )
    return new_repo_id, new_baseurl


# ---------------------------------------------------------------------------
# Per-repo capabilities
# ---------------------------------------------------------------------------

# openshift/release#84305: installer image builds pull RPMs from intranet hosts
# and must not land on build01.
CAPABILITIES_BY_REPO: Dict[Tuple[str, str], List[str]] = {
    ('openshift', 'installer'): ['intranet'],
}


# ---------------------------------------------------------------------------
# Cross-check against the OCP config in an openshift/release checkout
# ---------------------------------------------------------------------------

def _alternate_branches(branch: str) -> List[str]:
    alts = []
    m = re.match(r'^(release|openshift)-(\d+\.\d+)$', branch)
    if m:
        other = 'openshift' if m.group(1) == 'release' else 'release'
        alts.append(f'{other}-{m.group(2)}')
    if branch == 'master':
        alts.append('main')
    elif branch == 'main':
        alts.append('master')
    return alts


class ReleaseRepo:
    """Read OCP ci-operator configs from an openshift/release checkout."""

    def __init__(self, root: Path):
        self.config_dir = root / 'ci-operator' / 'config'
        self.repos_dir = root / 'core-services' / 'release-controller' / '_repos'
        self._cache: Dict[Tuple[str, str, str], Optional[dict]] = {}
        self._mirror_cache: Dict[Tuple[str, str], Optional[set]] = {}

    def mirror_repo_ids(self, version: str, rhel_tag: str) -> Optional[set]:
        """Repo ids the content mirror serves for one OCP version and RHEL.

        Reads ``ocp-{version}-{rhel_tag}.repo`` once and caches it. Returns
        None when the file doesn't exist, so callers fall back to the
        hardcoded rule.
        """
        key = (version, rhel_tag)
        if key not in self._mirror_cache:
            path = self.repos_dir / f'ocp-{version}-{rhel_tag}.repo'
            if path.is_file():
                self._mirror_cache[key] = set(_REPO_SECTION.findall(path.read_text()))
            else:
                self._mirror_cache[key] = None
                REPORT.warn(
                    f'Mirror definition {path.name} not found; used the hardcoded '
                    f'repo-name rule for {rhel_tag} repos'
                )
        return self._mirror_cache[key]

    def ocp_config_path(self, org: str, repo: str, branch: str) -> Path:
        return self.config_dir / org / repo / f'{org}-{repo}-{branch}.yaml'

    def ocp_config(self, org: str, repo: str, branch: str) -> Optional[dict]:
        key = (org, repo, branch)
        if key not in self._cache:
            path = self.ocp_config_path(org, repo, branch)
            self._cache[key] = yaml.safe_load(path.read_text()) if path.is_file() else None
        return self._cache[key]

    def resolve_branch(self, org: str, repo: str, branch: str) -> str:
        """Use the branch name the repo's OCP config uses.

        openshift/release#86173: etcd moved from openshift-X.Y to release-X.Y.
        openshift/release#85816: router moved from master to main.
        """
        if self.ocp_config_path(org, repo, branch).is_file():
            return branch
        for alt in _alternate_branches(branch):
            if self.ocp_config_path(org, repo, alt).is_file():
                REPORT.fix(
                    f'{org}/{repo}: branch {branch} -> {alt} (OCP config uses {alt}; '
                    f'openshift/release#86173, #85816)'
                )
                return alt
        REPORT.warn(
            f'{org}/{repo}: no OCP config for branch {branch} or its alternates; '
            f'confirm the branch name'
        )
        return branch

    def reconcile(self, org: str, repo: str, branch: str, config: dict):
        """Align a generated config with facts from the repo's OCP config."""
        ocp = self.ocp_config(org, repo, branch)
        if not ocp:
            return
        name = f'{org}/{repo}@{branch}'

        ocp_images = ocp.get('images') or []
        if isinstance(ocp_images, dict):
            ocp_images = ocp_images.get('items') or []
        ocp_by_dockerfile = {
            img.get('dockerfile_path'): img for img in ocp_images if img.get('dockerfile_path')
        }

        for img in _image_items(config):
            ocp_img = ocp_by_dockerfile.get(img.get('dockerfile_path'))
            if ocp_img and ocp_img.get('capabilities') and not img.get('capabilities'):
                img['capabilities'] = list(ocp_img['capabilities'])
                REPORT.fix(
                    f'{name}: {img.get("to")} capabilities {ocp_img["capabilities"]} '
                    f'(copied from OCP config; openshift/release#84305)'
                )
            path = img.get('dockerfile_path') or ''
            if not path.endswith('.rhel10'):
                sibling = f'{path}.rhel10'
                rhel10 = [p for p in ocp_by_dockerfile if p == sibling or (
                    p.endswith('.rhel10') and Path(p).parent == Path(path).parent
                )]
                if rhel10:
                    REPORT.warn(
                        f'{name}: {img.get("to")} builds {path}, but the OCP config also '
                        f'builds {rhel10[0]}. Check which one OKD needs '
                        f'(openshift/release#88570)'
                    )

        # Builder tags: warn when OCP uses a newer golang or openshift version.
        # openshift/release#84589 (golang 1.25 -> 1.26), #88570
        # (driver-toolkit builder -openshift-5.0 -> -openshift-5.1).
        ocp_builders = _builder_versions(ocp.get('base_images') or {})
        gen_builders = _builder_versions(config.get('base_images') or {})
        for rhel, (gen_go, gen_ocp, gen_tag) in gen_builders.items():
            if rhel not in ocp_builders:
                continue
            ocp_go, ocp_ver, ocp_tag = ocp_builders[rhel]
            if (ocp_go, ocp_ver) > (gen_go, gen_ocp):
                REPORT.warn(
                    f'{name}: builder {gen_tag} is older than the OCP config\'s {ocp_tag} '
                    f'(openshift/release#84589, #88570)'
                )


_BUILDER_TAG = re.compile(r'^(rhel-\d+)-golang-(\d+)\.(\d+)-openshift-(\d+)\.(\d+)$')


def _builder_versions(base_images: dict) -> Dict[str, Tuple[Tuple[int, int], Tuple[int, int], str]]:
    found: Dict[str, Tuple[Tuple[int, int], Tuple[int, int], str]] = {}
    for spec in base_images.values():
        tag = (spec or {}).get('tag', '')
        m = _BUILDER_TAG.match(tag)
        if not m:
            continue
        rhel = m.group(1)
        entry = ((int(m.group(2)), int(m.group(3))), (int(m.group(4)), int(m.group(5))), tag)
        if rhel not in found or entry[:2] > found[rhel][:2]:
            found[rhel] = entry
    return found


def _image_items(config: dict) -> List[dict]:
    images = config.get('images') or []
    if isinstance(images, dict):
        images = images.get('items') or []
    return images
