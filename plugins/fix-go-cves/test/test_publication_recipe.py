#!/usr/bin/env python3
"""Render actual recipes with real Git configuration; never publish anything."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]


class PublicationRecipe(unittest.TestCase):
    def setUp(self):
        scratch = PLUGIN.parents[1] / '.work/fix-go-cves-publication-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.env = {**os.environ, 'GIT_CEILING_DIRECTORIES': str(self.root)}
        self.git('init', '-q', '-b', 'fix-review')
        self.git('remote', 'add', 'origin', 'https://github.com/upstream/project.git')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.data = self.root / 'metadata.json'
        self.calls = self.root / 'calls.jsonl'
        stub = self.bin / 'gh'
        stub.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                        'with open(os.environ["RECIPE_CALLS"],"a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n'
                        'v=json.load(open(os.environ["RECIPE_DATA"])).get(sys.argv[-1])\n'
                        'if v is None: sys.exit(1)\nprint(json.dumps(v))\n')
        stub.chmod(0o755)
        self.env.update(PATH=str(self.bin) + ':' + self.env['PATH'],
                        RECIPE_DATA=str(self.data), RECIPE_CALLS=str(self.calls))
        self.metadata = {
            'repos/upstream/project': {'full_name': 'upstream/project', 'id': 1},
            'repos/developer/project': {'full_name': 'developer/project', 'id': 2,
                                       'source': {'id': 1}, 'owner': {'type': 'User'}},
        }
        source = (PLUGIN / 'scripts/fix-all.sh').read_text()
        start = source.index('    # Generate PR command')
        end = source.index('\n  fi\nelse\n  # Nothing to keep', start)
        self.renderer = ('set -euo pipefail\nsource "$1/lib.sh"\n'
                         'BRANCH=devel CURRENT_BRANCH=fix-review COMMIT_COUNT=1 GATE_REMAINING=0\n'
                         + source[start:end])

    def git(self, *arguments):
        return subprocess.run(['git', '-C', str(self.repo), *arguments], env=self.env,
                              text=True, capture_output=True, check=True).stdout.strip()

    def route(self, name='fork', url='https://github.com/developer/project.git'):
        self.git('remote', 'add', name, url)
        self.git('config', 'remote.pushDefault', name)

    def render(self):
        self.data.write_text(json.dumps(self.metadata))
        result = subprocess.run(['bash', '-c', self.renderer, 'recipe-test', str(PLUGIN / 'scripts')],
                                cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def recipe(self):
        output = self.render()
        self.assertIn('PR command:\n', output)
        tokens = shlex.split(output.split('PR command:\n', 1)[1].replace('\\\n', ''))
        split = tokens.index('&&')
        push, create = tokens[:split], tokens[split + 1:]
        self.assertEqual(push[:3], ['git', 'push', '--no-follow-tags'])
        self.assertEqual(push[-1], 'refs/heads/fix-review:refs/heads/fix-review')
        self.assertEqual(create[:3], ['gh', 'pr', 'create'])
        self.assertEqual(create[create.index('--repo') + 1], 'upstream/project')
        self.assertEqual(create[create.index('--base') + 1], 'devel')
        return push[3], create[create.index('--head') + 1]

    def withheld(self):
        output = self.render()
        self.assertNotIn('PR command:\n', output)
        self.assertNotIn('gh pr create', output)
        self.assertIn('could not be confirmed', output)
        return output

    def test_explicit_same_repository_route_needs_no_metadata(self):
        self.git('config', 'remote.pushDefault', 'origin')
        self.assertEqual(self.recipe(), ('origin', 'fix-review'))
        self.assertFalse(self.calls.exists())

    def test_confirmed_partial_recipe_preserves_remaining_count(self):
        self.git('config', 'remote.pushDefault', 'origin')
        self.renderer = self.renderer.replace('GATE_REMAINING=0', 'GATE_REMAINING=2')
        output = self.render()
        tokens = shlex.split(output.split('PR command:\n', 1)[1].replace('\\\n', ''))
        self.assertEqual(tokens[tokens.index('--title') + 1], 'Partial CVE fix in devel (2 unresolved)')

    def test_multiple_commits_render_plural_recipe(self):
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        for number in (1, 2):
            (self.repo / 'fixture').write_text(str(number))
            self.git('add', 'fixture')
            self.git('commit', '-qm', 'fixture')
        count = self.git('rev-list', '--count', 'HEAD')
        self.assertEqual(count, '2')
        self.git('config', 'remote.pushDefault', 'origin')
        self.renderer = self.renderer.replace('COMMIT_COUNT=1', 'COMMIT_COUNT=' + count)
        tokens = shlex.split(self.render().split('PR command:\n', 1)[1].replace('\\\n', ''))
        self.assertEqual(tokens[tokens.index('--title') + 1], 'Fix CVEs in devel')
        self.assertEqual(tokens[tokens.index('--body') + 1], 'See commit messages for details.')

    def test_branch_route_overrides_default_and_ignores_backup_order(self):
        self.route('aaa-backup', 'https://github.com/unrelated/project.git')
        self.git('remote', 'add', 'fork', 'https://github.com/developer/project.git')
        self.git('config', 'branch.fix-review.pushRemote', 'fork')
        self.assertEqual(self.recipe(), ('fork', 'developer:fix-review'))
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(calls, [
            ['api', '--hostname', 'github.com', 'repos/upstream/project'],
            ['api', '--hostname', 'github.com', 'repos/developer/project'],
        ])

    def test_unconfigured_or_multiple_candidates_do_not_imply_intent(self):
        self.git('remote', 'add', 'fork', 'https://github.com/developer/project.git')
        self.withheld()
        self.git('remote', 'add', 'another', 'https://github.com/another/project.git')
        self.withheld()
        self.assertFalse(self.calls.exists())

    def test_empty_branch_override_does_not_fall_back_to_default(self):
        self.route()
        self.git('config', 'branch.fix-review.pushRemote', '')
        self.withheld()
        self.assertFalse(self.calls.exists())

    def test_split_fetch_push_and_renamed_fork_use_confirmed_network(self):
        self.route(url='https://github.com/upstream/project.git')
        self.git('remote', 'set-url', '--push', 'fork', 'git@github.com:developer/renamed.git')
        self.metadata['repos/developer/renamed'] = {
            'full_name': 'developer/renamed', 'id': 2, 'source': {'id': 1}, 'owner': {'type': 'User'}}
        self.assertEqual(self.recipe(), ('fork', 'developer:fix-review'))
        self.git('remote', 'set-url', '--push', 'origin', 'git@github.com:developer/renamed.git')
        self.git('config', 'remote.pushDefault', 'origin')
        self.assertEqual(self.recipe(), ('origin', 'developer:fix-review'))

    def test_unrelated_same_name_repository_is_not_a_fork(self):
        self.route()
        self.metadata['repos/developer/project']['source']['id'] = 9
        self.withheld()

    def test_owner_substrings_do_not_change_confirmed_network_identity(self):
        self.route(url='https://github.com/upstream-developer/project.git')
        self.metadata['repos/upstream-developer/project'] = {
            'full_name': 'upstream-developer/project', 'id': 2,
            'source': {'id': 1}, 'owner': {'type': 'User'}}
        self.assertEqual(self.recipe(), ('fork', 'upstream-developer:fix-review'))

    def test_every_effective_push_url_must_be_unique(self):
        self.route()
        self.git('config', '--add', 'remote.fork.pushurl', 'https://github.com/developer/project.git')
        self.git('config', '--add', 'remote.fork.pushurl', 'https://github.com/backup/project.git')
        self.withheld()
        self.assertFalse(self.calls.exists())

    def test_multiple_base_urls_are_not_a_confirmed_identity(self):
        self.route()
        self.git('config', '--add', 'remote.origin.url', 'https://github.com/unrelated/project.git')
        self.withheld()
        self.assertFalse(self.calls.exists())

    def test_supported_transports_and_casing_preserve_same_base_identity(self):
        self.git('config', 'remote.pushDefault', 'origin')
        for url in ('https://GitHub.COM/Upstream/Project.git', 'git@github.com:upstream/project.git',
                    'ssh://git@github.com:443/upstream/project.git',
                    'ssh://git@ssh.github.com:443/upstream/project.git'):
            with self.subTest(url=url):
                self.git('remote', 'set-url', 'origin', url)
                self.assertEqual(self.recipe(), ('origin', 'fix-review'))
        self.assertFalse(self.calls.exists())

    def test_credential_bearing_or_non_github_destinations_are_not_printed(self):
        self.route()
        for url in ('https://secret-token@github.com/developer/project.git',
                    'https://github.com/developer/project.git?token=secret-token',
                    'git@gitlab.example.com:developer/project.git', str(self.root / 'local.git')):
            with self.subTest(url=url):
                self.git('remote', 'set-url', '--push', 'fork', url)
                output = self.withheld()
                self.assertNotIn('secret-token', output)
        self.assertFalse(self.calls.exists())

    def test_owner_override_cannot_authenticate_non_github_base(self):
        self.route()
        self.env['UPSTREAM_ORG'] = 'upstream'
        for url in ('git@gitlab.example.com:upstream/project.git', str(self.root / 'local.git')):
            with self.subTest(url=url):
                self.git('remote', 'set-url', 'origin', url)
                self.withheld()
        self.assertFalse(self.calls.exists())

    def test_unavailable_or_incomplete_metadata_withholds_without_failing(self):
        self.route()
        self.metadata = {}
        self.withheld()
        self.metadata = {'repos/upstream/project': {'full_name': 'upstream/project', 'id': 1},
                         'repos/developer/project': {'full_name': 'developer/project'}}
        self.withheld()

    def test_organization_fork_and_mirror_route_are_not_supported_recipes(self):
        self.route()
        self.metadata['repos/developer/project']['owner']['type'] = 'Organization'
        self.withheld()
        self.metadata['repos/developer/project']['owner']['type'] = 'User'
        self.git('config', 'remote.fork.mirror', 'true')
        self.withheld()


if __name__ == '__main__':
    unittest.main()
