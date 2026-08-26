from skillsaw import RepositoryContext


def _make_plugin(temp_dir, name, *, commands=()):
    plugin_dir = temp_dir / "plugins" / name
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(
        f'{{"name": "{name}", "version": "0.0.1", '
        f'"description": "test", "author": "test"}}'
    )
    if commands:
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir()
        for command in commands:
            (commands_dir / f"{command}.md").write_text(
                "---\ndescription: Test command\n---\n\n# Test\n"
            )
    return plugin_dir


class TestPluginCommandsProhibited:
    def test_plugin_without_commands_is_valid(self, temp_dir, plugin_commands_rule):
        _make_plugin(temp_dir, "skills-only")

        violations = plugin_commands_rule().check(RepositoryContext(temp_dir))

        assert violations == []

    def test_non_allowlisted_commands_are_prohibited(
        self, temp_dir, plugin_commands_rule
    ):
        plugin = _make_plugin(temp_dir, "new-plugin", commands=("test",))

        violations = plugin_commands_rule().check(RepositoryContext(temp_dir))

        assert len(violations) == 1
        assert violations[0].file_path == plugin / "commands" / "test.md"
        assert "new-plugin:test" in violations[0].message
        assert "new plugin commands are prohibited" in violations[0].message

    def test_allowlisted_commands_are_valid(self, temp_dir, plugin_commands_rule):
        _make_plugin(temp_dir, "grandfathered", commands=("existing",))
        rule = plugin_commands_rule({"allowlist": ["grandfathered:existing"]})

        violations = rule.check(RepositoryContext(temp_dir))

        assert violations == []

    def test_new_command_in_same_plugin_is_prohibited(
        self, temp_dir, plugin_commands_rule
    ):
        _make_plugin(temp_dir, "grandfathered", commands=("existing", "new"))
        rule = plugin_commands_rule({"allowlist": ["grandfathered:existing"]})

        violations = rule.check(RepositoryContext(temp_dir))

        assert len(violations) == 1
        assert "grandfathered:new" in violations[0].message
