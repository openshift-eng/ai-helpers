#!/usr/bin/env python3
"""Offline native-Git controls for mutation boundaries and failed exceptions."""
import base64
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

PLUGIN = Path(os.environ.get('CVE_FIX_TEST_PLUGIN', Path(__file__).resolve().parents[1]))


class TransactionFences(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[3] / '.work/fix-go-cves-transaction-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.scripts = self.root / 'plugin/scripts'
        shutil.copytree(PLUGIN / 'scripts', self.scripts, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(PLUGIN / 'subagents', self.root / 'plugin/subagents')
        # Graph/update outcomes are modeled; orchestration, Git, audits,
        # builds, policy writes and transaction cleanup remain the real code.
        with (self.scripts / 'lib.sh').open('a') as library:
            library.write('''
preflight_check() { return 0; }
if [[ "${CONTROL_NATIVE_GO:-false}" != true ]]; then
get_installed_version() {
  awk '$1 == "require" && $2 == "example.invalid/dep" { sub(/^v/, "", $3); print $3 }' "$1/go.mod"
}
module_go() {
  local d="$1" op="$2"; shift 2
  case "$op" in
    get) sed -i 's#example.invalid/dep v1.0.0#example.invalid/dep v1.0.1#' "$d/go.mod" ;;
    mod) return 0 ;;
    *) return 1 ;;
  esac
}
fi
''')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for tool in ('docker', 'podman'):
            (self.bin / tool).write_text('#!/bin/sh\nexit 1\n')
        (self.bin / 'grype').write_text('''#!/usr/bin/env python3
import json, os
from pathlib import Path
no_fix = os.environ.get('CONTROL_NO_FIX') == 'true'
match = {"artifact":{"type":"go-module","name":"example.invalid/dep","version":"1.0.0","locations":[{"path":"/go.mod"}]},
         "vulnerability":{"id":"CVE-TEST","severity":"High","fix":{"versions":[] if no_fix else ["1.0.1"],"state":"not-fixed" if no_fix else "fixed"}}}
ignored = no_fix and Path('.grype.yaml').exists() and 'CVE-TEST' in Path('.grype.yaml').read_text()
present = no_fix or 'example.invalid/dep v1.0.0' in Path('go.mod').read_text()
matches = [match] if present and not ignored else []
if os.environ.get('CONTROL_TWO_GROUPS') == 'true':
    second = json.loads(json.dumps(match))
    second['artifact']['name'] = 'example.invalid/second'
    second['vulnerability']['id'] = 'CVE-SECOND'
    matches.append(second)
print(json.dumps({"matches":matches,"ignoredMatches":[match] if ignored else []}))
''')
        for path in self.bin.iterdir():
            path.chmod(0o755)
        (self.root / 'tmp').mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(('CVE_FIX_', 'GIT_'))}
        self.env.update(CONTROL_NATIVE_GO='false', PATH=str(self.bin) + ':' + os.environ['PATH'], GOENV='off',
                        GOTOOLCHAIN='local', GOWORK='off', GOFLAGS='', GOPROXY='off',
                        GOSUMDB='off', GOEXPERIMENT=',', TMPDIR=str(self.root / 'tmp'),
                        XDG_CONFIG_HOME=str(self.root / 'config'), CVE_FIX_TEST_CMD='true',
                        GIT_CONFIG_NOSYSTEM='1', GIT_CEILING_DIRECTORIES=str(self.root))
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'go.mod').write_text('module example.invalid/root\n\ngo 1.24.0\n\nrequire example.invalid/dep v1.0.0\n')
        (self.repo / 'source').write_text('base\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')
        self.base = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], env=self.env, text=True).strip()

    def run_script(self, script, *args, **settings):
        return subprocess.run(['bash', str(self.scripts / script), *map(str, args)],
                              cwd=self.repo, env={**self.env, **settings}, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=30)

    def prepare_remote(self, name):
        remote = self.root / (name + '.git')
        subprocess.run(['git', 'clone', '--bare', '-q', str(self.repo), str(remote)],
                       env=self.env, check=True)
        self.git('remote', 'add', name, str(remote))
        self.git('fetch', '-q', name)
        return remote

    def engine(self, **settings):
        self.prepare_remote('origin')
        return self.run_script('fix-all.sh', self.repo, 'main', **settings)

    def state(self, **settings):
        path = self.root / 'state.env'
        values = dict(REPO=str(self.repo), BRANCH='main', BUILD_GO_VERSION='unknown',
                      HAS_LOCAL_GRYPE='false', CONTAINER_CMD='', BUILD_CMD='',
                      CVE_SCRIPTS=str(self.scripts), ENV_UNSET='', DIFF_IGNORE_ARGS='', UPSTREAM_REMOTE='origin')
        values.update(settings)
        path.write_text(''.join(f'{key}={shlex.quote(value)}\n' for key, value in values.items()))
        return path

    def test_detection_bounds_runtime_probes_and_preserves_fallbacks(self):
        probes, bounds = self.root / 'runtime-probes.jsonl', self.root / 'runtime-bounds'
        runtime = f'''#!{sys.executable}
import json, os, signal, subprocess, sys
from pathlib import Path
name = Path(sys.argv[0]).name
mode = os.environ['CONTROL_' + name.upper()]
record = {{'runtime':name, 'args':sys.argv[1:], 'pid':os.getpid()}}
if mode == 'hung':
    child = subprocess.Popen(['sleep', '300'])
    record['child'] = child.pid
    def terminate(signum, frame):
        child.wait()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
with open(os.environ['CONTROL_RUNTIME_PROBES'], 'a') as log:
    print(json.dumps(record), file=log)
if mode == 'hung':
    while True:
        signal.pause()
raise SystemExit(0 if mode == 'healthy' else 1)
'''
        for name in ('docker', 'podman'):
            (self.bin / name).write_text(runtime)
        # Verify the production caller requests 20 seconds, then exercise the
        # real helper's process-group cleanup with a shorter fixture deadline.
        with (self.scripts / 'lib.sh').open('a') as library:
            library.write('''
eval "$(declare -f bounded_command | sed '1s/bounded_command/native_bounded_command/')"
bounded_command() {
  printf '%s\\n' "$*" >> "$CONTROL_RUNTIME_BOUNDS"
  [[ "$1" == 20 ]] || return 99
  shift
  native_bounded_command .5 "$@"
}
''')
        cases = [('healthy', 'healthy', 'docker', ['docker']),
                 ('hung', 'healthy', 'podman', ['docker', 'podman']),
                 ('unavailable', 'unavailable', '', ['docker', 'podman']),
                 ('hung', 'hung', '', ['docker', 'podman'])]
        for docker, podman, expected, invoked in cases:
            with self.subTest(docker=docker, podman=podman):
                probes.write_text('')
                bounds.write_text('')
                started = time.monotonic()
                result = subprocess.run(
                    ['timeout', '--kill-after=1', '3', 'bash', str(self.scripts / 'detect.sh'), str(self.repo), 'main'],
                    cwd=self.repo, env={**self.env, 'CONTROL_DOCKER':docker, 'CONTROL_PODMAN':podman,
                                       'CONTROL_RUNTIME_PROBES':str(probes), 'CONTROL_RUNTIME_BOUNDS':str(bounds)},
                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
                self.assertLess(time.monotonic() - started, 3)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                state = Path(result.stdout.splitlines()[-1])
                selected = subprocess.check_output(
                    ['bash', '-c', 'source "$1"; printf "%s" "$CONTAINER_CMD"', 'bash', str(state)],
                    env=self.env, text=True)
                self.assertEqual(selected, expected)
                self.assertEqual(bounds.read_text().splitlines(), [f'20 {name} info' for name in invoked])
                records = [json.loads(line) for line in probes.read_text().splitlines()]
                self.assertEqual([record['runtime'] for record in records], invoked)
                for record in records:
                    self.assertEqual(record['args'], ['info'])
                    for pid in (record['pid'], record.get('child')):
                        if pid is not None:
                            with self.assertRaises(ProcessLookupError, msg=f'runtime process {pid} survived detection'):
                                os.kill(pid, 0)

    def native_source_fixture(self):
        proxy = self.root / 'proxy/example.invalid/dep/@v'
        proxy.mkdir(parents=True)
        for version in ('v1.0.0', 'v1.0.1'):
            mod = 'module example.invalid/dep\n\ngo 1.24.0\n'
            (proxy / (version + '.mod')).write_text(mod)
            (proxy / (version + '.info')).write_text(json.dumps({'Version': version, 'Time': '2026-01-01T00:00:00Z'}))
            with zipfile.ZipFile(proxy / (version + '.zip'), 'w') as archive:
                archive.writestr(f'example.invalid/dep@{version}/go.mod', mod)
                archive.writestr(f'example.invalid/dep@{version}/dep.go', 'package dep\nconst Value = 1\n')
        (proxy / 'list').write_text('v1.0.0\nv1.0.1\n')
        self.env.update(CONTROL_NATIVE_GO='true', CONTROL_SOURCE_SCAN_MODE='healthy', GOPROXY=(self.root / 'proxy').as_uri(),
                        GOPRIVATE='', GONOPROXY='none', GOMODCACHE=str(self.root / 'modcache'),
                        CONTROL_SOURCE_SCAN_LOG=str(self.root / 'source-scans.jsonl'))
        (self.repo / 'main.go').write_text('package main\nimport "example.invalid/dep"\nfunc main() { println(dep.Value) }\n')
        subprocess.run(['go', 'mod', 'tidy'], cwd=self.repo, env=self.env, check=True, capture_output=True)
        self.opaque = self.repo / 'opaque-tool'
        self.opaque.write_bytes(b'\x7fELF\x00UPX!\x00controlled opaque executable')
        self.opaque.chmod(0o755)
        self.git('add', '-A')
        self.git('commit', '-qm', 'native source and unrelated opaque tool')
        self.base = self.git('rev-parse', 'HEAD')
        (self.bin / 'grype').write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
if 'version' in sys.argv:
    print('grype 0.121.0'); raise SystemExit()
mode = os.environ.get('CONTROL_SOURCE_SCAN_MODE', 'healthy')
vulnerable = 'example.invalid/dep v1.0.0' in Path('go.mod').read_text()
matches = []
if vulnerable or mode == 'new':
    matches = [{"artifact":{"type":"go-module","name":"example.invalid/dep","version":"1.0.0" if vulnerable else "1.0.1","locations":[{"path":"/go.mod"}]},
                "vulnerability":{"id":"CVE-TEST" if vulnerable else "CVE-NEW","severity":"High","fix":{"versions":["1.0.1" if vulnerable else "1.0.2"],"state":"fixed"}}}]
with open(os.environ['CONTROL_SOURCE_SCAN_LOG'], 'a') as log:
    print(json.dumps({'vulnerable':vulnerable,'matches':matches}), file=log)
if mode == 'degraded': print('unable to update vulnerability database', file=sys.stderr)
print(json.dumps({} if mode == 'invalid' else {'matches':matches,'ignoredMatches':[]}))
raise SystemExit(17 if mode == 'nonzero' else 0)
''')
        # Model the scanner's typed degradation output; --no-update does not
        # infer a fresh database failure merely from an update warning.
        with (self.scripts / 'lib.sh').open('a') as library:
            library.write('''
if [[ "${CONTROL_SOURCE_SCAN_MODE:-}" == degraded ]]; then
  run_grype() { command grype .; GRYPE_DB_DEGRADED=1; }
fi
''')

    def test_native_source_fix_ignores_unrelated_binary_coverage(self):
        self.native_source_fixture()
        result = self.run_script('fix-package.sh', self.state(HAS_LOCAL_GRYPE='true'),
                                 'example.invalid/dep', '1.0.1', 'CVE-TEST')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        version = subprocess.check_output(['go', 'list', '-m', '-f', '{{.Version}}', 'example.invalid/dep'],
                                          cwd=self.repo, env=self.env, text=True).strip()
        self.assertEqual(version, 'v1.0.1')
        self.assertIn('packed/opaque binary', result.stderr)
        self.assertNotEqual(self.git('rev-parse', 'HEAD'), self.base)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_opaque_engine_retains_native_source_fix_but_blocks_readiness(self):
        self.native_source_fixture()
        opaque = self.opaque.read_bytes()
        evidence, tested = self.root / 'evidence', self.root / 'tested-head'
        result = self.engine(CVE_FIX_EVIDENCE_DIR=str(evidence),
                             CVE_FIX_TEST_CMD=f'git rev-parse HEAD > {shlex.quote(str(tested))}')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('FIXED: example.invalid/dep', result.stdout)
        self.assertIn('example.invalid/dep v1.0.1', (self.repo / 'go.mod').read_text())
        receipt = json.loads((evidence / 'run.json').read_text())
        self.assertEqual(receipt['head'], receipt['tested_head'])
        self.assertEqual(tested.read_text().strip(), receipt['head'])
        self.assertNotEqual(receipt['head'], self.base)
        self.assertEqual(receipt['phases']['final_gate'], 'completed')
        self.assertTrue(json.loads((evidence / 'final-gate-status.json').read_text())['coverage_unknown'])
        self.assertEqual(json.loads((evidence / 'final-gate.json').read_text())['matches'], [])
        self.assertNotIn('PR command:', result.stdout)
        self.assertNotIn('Clean: no actionable CVEs remain.', result.stdout)
        self.assertEqual(self.opaque.read_bytes(), opaque)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_native_source_scan_still_rolls_back_new_findings_with_opaque_tool(self):
        self.native_source_fixture()
        result = self.run_script('fix-package.sh', self.state(HAS_LOCAL_GRYPE='true'),
                                 'example.invalid/dep', '1.0.1', 'CVE-TEST', CONTROL_SOURCE_SCAN_MODE='new')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('update introduces new source findings', result.stdout)
        scans = [json.loads(line) for line in (self.root / 'source-scans.jsonl').read_text().splitlines()]
        self.assertTrue(any(not scan['vulnerable'] for scan in scans))
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_native_source_scan_health_still_blocks_repairs(self):
        self.native_source_fixture()
        for mode in ('degraded', 'invalid', 'nonzero'):
            with self.subTest(mode=mode):
                self.git('reset', '--hard', '--quiet', self.base)
                result = self.run_script('fix-package.sh', self.state(HAS_LOCAL_GRYPE='true'),
                                         'example.invalid/dep', '1.0.1', 'CVE-TEST', CONTROL_SOURCE_SCAN_MODE=mode)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('could not establish a baseline', result.stdout)
                self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)
                self.assertEqual(self.git('status', '--porcelain'), '')

    def test_binary_aware_prior_fix_check_still_requires_coverage(self):
        self.native_source_fixture()
        subprocess.run(['go', 'get', 'example.invalid/dep@v1.0.1'], cwd=self.repo, env=self.env,
                       check=True, capture_output=True)
        self.git('add', '-A')
        self.git('commit', '-qm', 'prior source update')
        before = self.git('rev-parse', 'HEAD')
        requirements = base64.b64encode(json.dumps([{'cve': 'CVE-TEST', 'versions': ['1.0.0']}]).encode()).decode()
        result = self.run_script('fix-package.sh', self.state(HAS_LOCAL_GRYPE='true'),
                                 'example.invalid/dep', '1.0.0', 'CVE-TEST', CVE_FIX_REQUIREMENTS_B64=requirements)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('fixed by a prior dependency update', result.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_engine_binds_tracking_base_separately_from_fork_and_checkout_default(self):
        tests, license_head = self.root / 'tested-head', self.root / 'license-head'
        policy = 'ignore:\n  # Keep maintainer policy.\n  - vulnerability: CVE-KEEP\n    package:\n      name: example.invalid/retained\n'
        (self.repo / '.grype.yaml').write_text(policy)
        (self.repo / 'Makefile').write_text('licensecheck:\n\t@git rev-parse HEAD > ' + shlex.quote(str(license_head)) + '\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'selected source policy and license command')
        base = self.git('rev-parse', 'HEAD')
        source = self.prepare_remote('source')
        fork = self.prepare_remote('fork')
        subprocess.run(['git', '-C', str(fork), 'update-ref', 'refs/heads/main', self.base], env=self.env, check=True)
        self.git('fetch', '-q', 'fork')
        self.git('config', 'branch.main.remote', 'source')
        self.git('config', 'branch.main.merge', 'refs/heads/main')
        self.git('config', 'checkout.defaultRemote', 'fork')
        self.git('config', 'remote.pushDefault', 'fork')
        before_config = (self.repo / '.git/config').read_bytes()
        before_refs = {name: value for value, name in (line.split(' ', 1) for line in self.git('show-ref').splitlines())}
        evidence = self.root / 'evidence'
        result = self.run_script('fix-all.sh', self.repo, 'main', CVE_FIX_EVIDENCE_DIR=str(evidence),
                                 CVE_FIX_TEST_CMD=f'git rev-parse HEAD > {shlex.quote(str(tests))}')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = json.loads((evidence / 'run.json').read_text())
        self.assertEqual(receipt['base_commit'], base)
        self.assertEqual(receipt['head'], receipt['tested_head'])
        for marker in (tests, license_head):
            self.assertEqual(marker.read_text().strip(), receipt['head'])
        self.assertEqual(receipt['license_command'], 'make licensecheck')
        self.assertEqual(receipt['license_exit_code'], 0)
        self.assertIn('example.invalid/dep v1.0.1', (self.repo / 'go.mod').read_text())
        self.assertEqual((self.repo / '.grype.yaml').read_text(), policy)
        self.assertEqual(self.git('rev-list', '--count', base + '..HEAD'), '1')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual((self.repo / '.git/config').read_bytes(), before_config)
        for name, value in before_refs.items():
            self.assertEqual(self.git('rev-parse', name), value)
        for remote, pin in ((source, base), (fork, self.base)):
            self.assertEqual(subprocess.check_output(['git', '-C', str(remote), 'rev-parse', 'main'], env=self.env, text=True).strip(), pin)

    def test_failed_new_ignore_never_certifies_uncommitted_policy(self):
        hook = self.repo / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        result = self.engine(CONTROL_NO_FIX='true')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse((self.repo / '.grype.yaml').exists())
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)
        self.assertNotIn('Clean: no actionable CVEs remain.', result.stdout)

    def test_failed_ignore_preserves_committed_policy(self):
        policy = '# Maintainer policy\nignore: []\n'
        (self.repo / '.grype.yaml').write_text(policy)
        self.git('add', '.grype.yaml')
        self.git('commit', '-qm', 'policy')
        hook = self.repo / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        result = self.engine(CONTROL_NO_FIX='true')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual((self.repo / '.grype.yaml').read_text(), policy)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_initial_build_cannot_rebaseline_restricted_go_minor(self):
        result = self.engine(CVE_FIX_GO_MINOR_GUARD='true',
                             CVE_FIX_BUILD_CMD="sed -i 's/go 1.24.0/go 1.25.0/' go.mod")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('--- Fixing CVEs ---', result.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)
        self.assertIn('go 1.24.0', (self.repo / 'go.mod').read_text())

    def test_completed_fix_then_abort_keeps_existing_branch_rollback(self):
        real_mktemp = shlex.quote(shutil.which('mktemp'))
        (self.bin / 'mktemp').write_text(f'''#!/bin/sh
case "$*" in *cve-fix-subagents-*) exit 1 ;; esac
exec {real_mktemp} "$@"
''')
        (self.bin / 'mktemp').chmod(0o755)
        result = self.engine()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('FIXED: example.invalid/dep', result.stdout)
        self.assertEqual(self.git('branch', '--show-current'), 'main')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)
        self.assertNotIn('fix-main-cves-', self.git('branch', '--list'))
        self.assertNotIn('no longer matches', result.stderr)

    def test_unrelated_initial_build_commit_is_preserved_and_blocked(self):
        result = self.engine(CVE_FIX_BUILD_CMD='printf "unexpected\\n" > source; git commit -qam unexpected')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('--- Fixing CVEs ---', result.stdout)
        self.assertEqual(self.git('log', '-1', '--format=%s'), 'unexpected')
        self.assertTrue(self.git('branch', '--show-current').startswith('fix-main-cves-'))
        self.assertEqual((self.repo / 'source').read_text(), 'unexpected\n')

    def test_same_commit_ref_change_during_tests_blocks(self):
        result = self.engine(CVE_FIX_TEST_CMD='git checkout -qb other')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.git('branch', '--show-current'), 'other')
        self.assertNotIn('PR command:', result.stdout)

    def test_initial_clean_ownership_loss_stops_before_build(self):
        self.git('branch', 'user-work')
        marker = self.root / 'build-started'
        clean = 'git checkout -q user-work; printf "user change\\n" > source; git add source'
        result = self.engine(CVE_FIX_CLEAN_CMD=clean, CVE_FIX_BUILD_CMD=f'touch {shlex.quote(str(marker))}')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual((self.repo / 'source').read_text(), 'user change\n')
        self.assertIn('+user change', self.git('diff', '--cached'))

    def native_edits(self):
        with (self.scripts / 'lib.sh').open('a') as library:
            library.write('''
get_installed_version() { awk -v p="$2" '$1 == "require" && $2 == p { sub(/^v/, "", $3); print $3 }' "$1/go.mod"; }
module_go() {
  local d="$1" op="$2"; shift 2
  case "$op" in
    get) local p="${1%@*}" v="${1#*@}"; sed -i "s#$p v[0-9.]*#$p $v#" "$d/go.mod" ;;
    mod) if [ "$1" = edit ]; then GOTOOLCHAIN=local go -C "$d" mod "$@"; fi ;;
    *) return 1 ;;
  esac
}
''')

    def test_verification_ownership_loss_stops_second_repair(self):
        self.verification_repair_loss()

    def test_failed_stale_ignore_amend_stops_second_repair(self):
        self.verification_repair_loss(amend=True)

    def test_failed_stale_ignore_amend_cannot_be_absorbed_by_next_repair(self):
        self.verification_repair_loss(amend=True, move=False)

    def verification_repair_loss(self, amend=False, move=True):
        self.native_edits()
        with (self.repo / 'go.mod').open('a') as module:
            module.write('require example.invalid/second v1.0.0\n')
        if amend:
            (self.repo / '.grype.yaml').write_text('ignore:\n  - vulnerability: CVE-TEST\n    package:\n      name: example.invalid/dep\n      type: go-module\n    fix-state: not-fixed\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'verification fixture')
        self.git('branch', 'user-work')
        self.git('checkout', '-qb', 'fix-test')
        if amend:
            counter = shlex.quote(str(self.root / 'commit-count'))
            movement = 'git reset --hard --quiet HEAD; git checkout -q user-work; printf "user change\\n" > source; git add source; ' if move else ''
            hook = self.repo / '.git/hooks/pre-commit'
            hook.write_text(f'#!/bin/sh\nn=$(cat {counter} 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > {counter}\nif [ "$n" = 2 ]; then {movement}exit 1; fi\n')
            hook.chmod(0o755)
        reports = self.root / 'reports'
        reports.mkdir()
        import json
        matches = []
        for package, cve in (('dep', 'CVE-TEST'), ('second', 'CVE-SECOND')):
            matches.append({'artifact': {'type': 'go-module', 'name': 'example.invalid/' + package,
                                         'locations': [{'path': '/go.mod'}]},
                            'vulnerability': {'id': cve, 'fix': {'versions': ['1.0.1']}}})
        (reports / 'final-scan.json').write_text(json.dumps({'matches': matches}))
        report = reports / 'scan-regression.evidence'
        report.write_text('NEW: CVE-TEST (example.invalid/dep 1.0.0 High 1.0.1)\n'
                          'NEW: CVE-SECOND (example.invalid/second 1.0.0 High 1.0.1)\n')
        build = 'git checkout -- go.mod; git checkout -q user-work; printf "user change\\n" > source; git add source; exit 1'
        state = self.state(BUILD_CMD='' if amend else build)
        command = 'source "$1/lib.sh"; load_state "$2"; subagent_fix_scan_regression "$2" "$3" "$1"'
        result = subprocess.run(['bash', '-c', command, 'repair', str(self.scripts), str(state), str(report)],
                                cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('Attempting fix: example.invalid/second', result.stdout)
        if move:
            self.assertEqual((self.repo / 'source').read_text(), 'user change\n')
            self.assertIn('+user change', self.git('diff', '--cached'))
        else:
            self.assertIn('.grype.yaml', self.git('diff', '--cached', '--name-only'))
            self.assertEqual(self.git('branch', '--show-current'), 'fix-test')

    def test_partial_stdlib_commit_continues_to_next_group_and_tests(self):
        self.native_edits()
        tools = self.repo / 'tools'
        tools.mkdir()
        (tools / 'go.mod').write_text('module example.invalid/tools\n\ngo 1.24.0\ntoolchain go1.24.0-custom\n')
        with (self.repo / 'go.mod').open('a') as module:
            module.write('require zz.invalid/next v1.0.0\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'partial stdlib fixture')
        (self.bin / 'grype').write_text('''#!/usr/bin/env python3
import json
from pathlib import Path
def hit(package, cve, version, locations):
    return {"artifact":{"type":"go-module","name":package,"locations":[{"path":p} for p in locations]},"vulnerability":{"id":cve,"severity":"High","fix":{"versions":[version],"state":"fixed"}}}
root = Path('go.mod').read_text()
locations = ['/tools/go.mod'] if 'toolchain go1.24.1' in root else ['/go.mod','/tools/go.mod']
matches = [hit('stdlib','CVE-STDLIB','1.24.1',locations)]
if 'zz.invalid/next v1.0.0' in root:
    matches.append(hit('zz.invalid/next','CVE-NEXT','1.0.1',['/go.mod']))
print(json.dumps({'matches':matches}))
''')
        marker = self.root / 'tests-ran'
        result = self.engine(CVE_FIX_TEST_CMD=f'touch {shlex.quote(str(marker))}')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('RETAINED_HEAD:', result.stdout)
        self.assertIn('FIXED: zz.invalid/next', result.stdout)
        self.assertTrue(marker.exists(), result.stdout + result.stderr)
        self.assertIn('toolchain go1.24.1', (self.repo / 'go.mod').read_text())
        self.assertIn('go1.24.0-custom', (tools / 'go.mod').read_text())
        self.assertNotIn('checkout moved', result.stdout + result.stderr)

    def verification_stdlib(self, mode='fixed'):
        self.native_edits()
        if mode == 'partial':
            (self.repo / 'tools').mkdir()
            (self.repo / 'tools/go.mod').write_text('module example.invalid/tools\n\ngo 1.24.0\ntoolchain go1.24.0-custom\n')
            self.git('add', 'tools/go.mod')
            self.git('commit', '-qm', 'custom toolchain fixture')
        requirements = [['1.24.1', '1.25.1'], ['1.24.2', '1.25.2']]
        if mode == 'disjoint':
            requirements = [['1.24.1'], ['1.25.2']]
        # Candidate validation still sees only the original dependency finding.
        # The committed repair exposes stdlib findings in verification; the
        # controlled scanner then observes the actual native Go toolchain edit.
        (self.bin / 'grype').write_text('''#!/usr/bin/env python3
import json, subprocess
from pathlib import Path
root = Path('go.mod').read_text()
committed = subprocess.check_output(['git', 'show', 'HEAD:go.mod'], text=True)
def hit(package, cve, version, fixes, location):
    return {"artifact":{"type":"go-module","name":package,"version":version,"locations":[{"path":location}]},
            "vulnerability":{"id":cve,"severity":"High","fix":{"versions":fixes,"state":"fixed"}}}
matches = []
if 'example.invalid/dep v1.0.0' in root:
    matches = [hit('example.invalid/dep','CVE-TEST','1.0.0',['1.0.1'],'/go.mod')]
elif 'example.invalid/dep v1.0.1' in committed:
    patched = 'toolchain go1.24.2' in root
''' + f'''
    if not patched or {mode == 'partial'!r}:
        location = '/tools/bin/app' if patched else '/bin/app'
        matches = [hit('stdlib',cve,'go1.24.0',fixes,location)
                   for cve,fixes in zip(('CVE-STD-A','CVE-STD-B'),{requirements!r})]
print(json.dumps({{'matches':matches}}))
''')
        marker = self.root / 'tested-head'
        evidence = self.root / 'evidence'
        result = self.engine(CVE_FIX_TEST_CMD=f'git rev-parse HEAD > {shlex.quote(str(marker))}',
                             CVE_FIX_EVIDENCE_DIR=str(evidence), CVE_FIX_GO_MINOR_GUARD='true')
        self.assertTrue(marker.is_file(), result.stdout + result.stderr)
        self.assertEqual(marker.read_text().strip(), self.git('rev-parse', 'HEAD'), result.stdout + result.stderr)
        self.assertIn('example.invalid/dep v1.0.1', (self.repo / 'go.mod').read_text())
        self.assertEqual(self.git('status', '--porcelain'), '')
        return result, json.loads((evidence / 'run.json').read_text())

    def test_verification_stdlib_uses_grouped_go_fix_and_tests_retained_commit(self):
        result, receipt = self.verification_stdlib()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('toolchain go1.24.2', (self.repo / 'go.mod').read_text())
        self.assertIn('\ngo 1.24.0\n', (self.repo / 'go.mod').read_text())
        self.assertIn('FIXED: stdlib go 1.24.2 for CVE-STD-A CVE-STD-B', result.stdout)
        self.assertNotIn('FIXED: stdlib v1.25.2', result.stdout)
        message = self.git('log', '-1', '--format=%B')
        for cve in ('CVE-STD-A', 'CVE-STD-B'):
            self.assertIn('Fixes: ' + cve, message)
        self.assertIn('Signed-off-by: Test <test@example.invalid>', message)
        self.assertEqual(receipt['verification_exit_code'], 0)
        self.assertEqual(receipt['tested_head'], receipt['head'])

    def test_verification_stdlib_rejects_disjoint_advisory_streams(self):
        result, receipt = self.verification_stdlib('disjoint')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('no single Go release stream is explicitly fixed for every grouped CVE', result.stdout)
        self.assertNotIn('toolchain', (self.repo / 'go.mod').read_text())
        self.assertNotIn('FIXED: stdlib', result.stdout)
        self.assertEqual(receipt['test_exit_code'], 0)

    def test_verification_partial_stdlib_commit_keeps_ownership_and_runs_tests(self):
        result, receipt = self.verification_stdlib('partial')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('RETAINED_HEAD:', result.stdout)
        self.assertIn('toolchain go1.24.2', (self.repo / 'go.mod').read_text())
        self.assertIn('go1.24.0-custom', (self.repo / 'tools/go.mod').read_text())
        self.assertNotIn('FIXED: stdlib', result.stdout)
        self.assertEqual(receipt['test_exit_code'], 0)
        self.assertNotIn('checkout ownership', result.stdout + result.stderr)

    def test_failed_verification_ownership_loss_never_runs_tests(self):
        self.verification_loss()

    def test_failed_verification_unowned_commit_never_runs_tests(self):
        self.verification_loss(commit=True)

    def verification_loss(self, commit=False):
        self.native_edits()
        self.git('branch', 'user-work')
        scan_marker = self.root / 'verification-findings'
        (self.bin / 'grype').write_text('''#!/usr/bin/env python3
import json
from pathlib import Path
def hit(package, cve, version):
    return {"artifact":{"type":"go-module","name":package,"locations":[{"path":"/go.mod"}]},"vulnerability":{"id":cve,"severity":"High","fix":{"versions":[version],"state":"fixed"}}}
''' + f'''
if Path({str(scan_marker)!r}).exists():
    matches = [hit('example.invalid/dep','CVE-REGRESSION','1.0.2'),hit('example.invalid/second','CVE-SECOND','1.0.1')]
else:
    matches = [hit('example.invalid/dep','CVE-TEST','1.0.1')] if 'example.invalid/dep v1.0.0' in Path('go.mod').read_text() else []
print(json.dumps({{'matches':matches}}))
''')
        counter = self.root / 'build-count'
        movement = 'git commit -qm unowned;' if commit else 'git checkout -q user-work;'
        build = (f'n=$(cat {shlex.quote(str(counter))} 2>/dev/null || echo 0); n=$((n+1)); '
                 f'echo "$n" > {shlex.quote(str(counter))}; '
                 f'if [ "$n" = 3 ]; then touch {shlex.quote(str(scan_marker))}; fi; '
                 'if [ "$n" = 4 ]; then git checkout -- go.mod; '
                 + ('' if commit else movement)
                 + 'printf "user change\\n" > source; git add source; '
                 + (movement if commit else '') + 'exit 1; fi')
        tests = self.root / 'tests-ran'
        result = self.engine(CVE_FIX_BUILD_CMD=build, CVE_FIX_TEST_CMD=f'touch {shlex.quote(str(tests))}')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('Verification iteration', result.stdout)
        self.assertFalse(tests.exists(), result.stdout + result.stderr)
        self.assertNotIn('Attempting fix: example.invalid/second', result.stdout)
        self.assertEqual(counter.read_text().strip(), '4')
        self.assertEqual((self.repo / 'source').read_text(), 'user change\n')
        if commit:
            self.assertEqual(self.git('log', '-1', '--format=%s'), 'unowned')
        else:
            self.assertIn('+user change', self.git('diff', '--cached'))

    def test_moved_checkout_stops_next_package_dispatch(self):
        self.git('branch', 'user-work')
        build = ('if [ "${CVE_FIX_EVIDENCE_PHASE:-}" != initial ]; then '
                 'git checkout -- go.mod && git checkout -q user-work && '
                 'printf "user change\\n" > source && git add source; exit 1; fi')
        result = self.engine(CONTROL_TWO_GROUPS='true', CVE_FIX_BUILD_CMD=build)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('--- Fixing: example.invalid/dep', result.stdout)
        self.assertNotIn('--- Fixing: example.invalid/second', result.stdout)
        self.assertNotIn('Verification iteration', result.stdout)
        self.assertEqual(self.git('branch', '--show-current'), 'user-work')
        self.assertEqual((self.repo / 'source').read_text(), 'user change\n')
        self.assertIn('+user change', self.git('diff', '--cached'))

    def test_package_failure_preserves_moved_checkout_index(self):
        self.git('branch', 'user-work')
        self.git('checkout', '-qb', 'fix-test')
        build = ('git checkout -- go.mod && git checkout -q user-work && '
                 'printf "user change\\n" > source && git add source && exit 1')
        state = self.state(BUILD_CMD=build)
        result = self.run_script('fix-package.sh', state, 'example.invalid/dep', '1.0.1', 'CVE-TEST')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.git('branch', '--show-current'), 'user-work')
        self.assertEqual((self.repo / 'source').read_text(), 'user change\n')
        self.assertIn('+user change', self.git('diff', '--cached'))
        self.assertTrue(list((self.root / 'tmp').glob('cve-dependency-before.*')))

    def test_stdlib_commit_failure_preserves_moved_checkout_index(self):
        self.git('branch', 'user-work')
        self.git('checkout', '-qb', 'fix-test')
        # Stdlib file edits use native Go; only the failed Git boundary moves.
        with (self.scripts / 'lib.sh').open('a') as library:
            library.write('\nmodule_go() { local d="$1"; shift; GOTOOLCHAIN=local go -C "$d" "$@"; }\n')
        real_git = shlex.quote(shutil.which('git'))
        (self.bin / 'git').write_text(f'''#!/bin/sh
if [ "$1" = commit ]; then
  {real_git} reset --quiet HEAD -- go.mod
  {real_git} checkout -- go.mod
  {real_git} checkout -q user-work
  printf 'user change\\n' > source
  {real_git} add source
  exit 1
fi
exec {real_git} "$@"
''')
        (self.bin / 'git').chmod(0o755)
        result = self.run_script('fix-stdlib.sh', self.state(), '1.24.1', '', 'CVE-TEST')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git('branch', '--show-current'), 'user-work')
        self.assertEqual((self.repo / 'source').read_text(), 'user change\n')
        self.assertIn('+user change', self.git('diff', '--cached'))

    def test_stdlib_nested_edit_failure_rolls_back_all_modules(self):
        _, before = self.stdlib_nested_edit_failure()
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertNotIn('toolchain', (self.repo / 'go.mod').read_text())
        self.assertIn('module example.invalid/tools', (self.repo / 'tools/go.mod').read_text())

    def test_stdlib_nested_edit_failure_preserves_moved_checkout_index(self):
        result, before = self.stdlib_nested_edit_failure(move=True)
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertEqual(self.git('branch', '--show-current'), 'user-work')
        self.assertEqual((self.repo / 'source').read_text(), 'user change\n')
        self.assertEqual(self.git('diff', '--cached', '--name-only'), 'source')
        self.assertIn('+user change', self.git('diff', '--cached'))
        self.assertIn('checkout moved; preserving its files and index', result.stderr)

    def test_stdlib_review_before_edits_preserves_caller_index(self):
        (self.repo / 'go.work').write_text('go 1.24.0\nuse .\n')
        self.git('add', 'go.work')
        self.git('commit', '-qm', 'workspace policy')
        before = self.git('rev-parse', 'HEAD')
        (self.repo / 'source').write_text('caller work\n')
        self.git('add', 'source')
        result = self.run_script('fix-stdlib.sh', self.state(), '1.24.1', '', 'CVE-TEST')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertEqual((self.repo / 'source').read_text(), 'caller work\n')
        self.assertIn('+caller work', self.git('diff', '--cached'))

    def stdlib_nested_edit_failure(self, move=False):
        tools = self.repo / 'tools'
        tools.mkdir()
        (tools / 'go.mod').write_text('module example.invalid/tools\n\ngo 1.24.0\n')
        self.git('add', 'tools/go.mod')
        self.git('commit', '-qm', 'second module')
        before = self.git('rev-parse', 'HEAD')
        self.git('branch', 'user-work')
        self.git('checkout', '-qb', 'fix-test')
        self.native_edits()
        # Fail a real nested Go edit only after the first module was changed.
        first_edit = self.root / 'first-module-before-failure'
        movement = 'git checkout -q user-work; printf "user change\\n" > source; git add source;' if move else ''
        real_go = shlex.quote(shutil.which('go'))
        (self.bin / 'go').write_text(f'''#!/bin/sh
if [ "$1" = -C ] && [ "$2" = tools ] && [ "$3" = mod ] && [ "$4" = edit ] && [ "${{5#-toolchain=}}" != "$5" ]; then
  cat go.mod > {shlex.quote(str(first_edit))}
  {movement}
  printf 'invalid metadata\n' > tools/go.mod
fi
exec {real_go} "$@"
''')
        (self.bin / 'go').chmod(0o755)
        result = self.run_script('fix-stdlib.sh', self.state(), '1.24.1', '', 'CVE-TEST')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('unknown directive', result.stderr)
        self.assertIn('toolchain go1.24.1', first_edit.read_text())
        self.assertNotIn('RETAINED_HEAD:', result.stdout)
        return result, before


if __name__ == '__main__':
    unittest.main()
