from pathlib import Path

from skillsaw import RepositoryContext


def _make_plugin(temp_dir, name, owners_content="approvers:\n- admin\n"):
    plugin_dir = temp_dir / "plugins" / name
    plugin_dir.mkdir(parents=True)
    claude_dir = plugin_dir / ".claude-plugin"
    claude_dir.mkdir()
    (claude_dir / "plugin.json").write_text(
        f'{{"name": "{name}", "version": "0.0.1", "description": "test", "author": "test"}}'
    )
    if owners_content is not None:
        (plugin_dir / "OWNERS").write_text(owners_content)
    return plugin_dir


class TestPluginOwnersRequired:
    def test_no_violations_with_owners(self, temp_dir, owners_rule):
        _make_plugin(temp_dir, "test-plugin")

        ctx = RepositoryContext(temp_dir)
        rule = owners_rule()
        violations = rule.check(ctx)
        assert len(violations) == 0

    def test_no_violations_with_subdirs(self, temp_dir, owners_rule):
        plugin = _make_plugin(temp_dir, "test-plugin")
        (plugin / "commands").mkdir()
        (plugin / "skills" / "my-skill").mkdir(parents=True)

        ctx = RepositoryContext(temp_dir)
        rule = owners_rule()
        violations = rule.check(ctx)
        assert len(violations) == 0

    def test_violation_when_plugin_missing_owners(self, temp_dir, owners_rule):
        _make_plugin(temp_dir, "test-plugin", owners_content=None)

        ctx = RepositoryContext(temp_dir)
        rule = owners_rule()
        violations = rule.check(ctx)
        assert len(violations) == 1
        assert "missing an OWNERS file" in violations[0].message

    def test_violation_when_owners_empty(self, temp_dir, owners_rule):
        _make_plugin(temp_dir, "test-plugin", owners_content="")

        ctx = RepositoryContext(temp_dir)
        rule = owners_rule()
        violations = rule.check(ctx)
        assert len(violations) == 1
        assert "empty OWNERS file" in violations[0].message

    def test_multiple_plugins(self, temp_dir, owners_rule):
        _make_plugin(temp_dir, "good-plugin")
        _make_plugin(temp_dir, "bad-plugin", owners_content=None)

        ctx = RepositoryContext(temp_dir)
        rule = owners_rule()
        violations = rule.check(ctx)
        assert len(violations) == 1
        assert "bad-plugin" in violations[0].message
