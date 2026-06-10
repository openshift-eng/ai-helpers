from pathlib import Path


def _make_plugin_with_agent(temp_dir, plugin_name, agent_name, frontmatter):
    plugin_dir = temp_dir / "plugins" / plugin_name
    plugin_dir.mkdir(parents=True)
    claude_dir = plugin_dir / ".claude-plugin"
    claude_dir.mkdir()
    (claude_dir / "plugin.json").write_text(
        f'{{"name": "{plugin_name}", "version": "0.0.1", '
        f'"description": "test", "author": "test"}}'
    )
    agents_dir = plugin_dir / "agents"
    agents_dir.mkdir()
    agent_file = agents_dir / f"{agent_name}.md"
    agent_file.write_text(f"---\n{frontmatter}\n---\n\nAgent body.\n")
    return agent_file


class TestOpencodeAgentColor:
    def test_hex_color_valid(self, temp_dir, opencode_color_rule):
        _make_plugin_with_agent(
            temp_dir, "my-plugin", "my-agent",
            'name: my-agent\ncolor: "#00FFFF"',
        )
        from skillsaw import RepositoryContext
        ctx = RepositoryContext(temp_dir)
        violations = opencode_color_rule().check(ctx)
        assert len(violations) == 0

    def test_preset_color_valid(self, temp_dir, opencode_color_rule):
        _make_plugin_with_agent(
            temp_dir, "my-plugin", "my-agent",
            "name: my-agent\ncolor: primary",
        )
        from skillsaw import RepositoryContext
        ctx = RepositoryContext(temp_dir)
        violations = opencode_color_rule().check(ctx)
        assert len(violations) == 0

    def test_css_color_name_invalid(self, temp_dir, opencode_color_rule):
        _make_plugin_with_agent(
            temp_dir, "my-plugin", "my-agent",
            "name: my-agent\ncolor: cyan",
        )
        from skillsaw import RepositoryContext
        ctx = RepositoryContext(temp_dir)
        violations = opencode_color_rule().check(ctx)
        assert len(violations) == 1
        assert "cyan" in violations[0].message

    def test_no_color_field_valid(self, temp_dir, opencode_color_rule):
        _make_plugin_with_agent(
            temp_dir, "my-plugin", "my-agent",
            "name: my-agent\ndescription: no color",
        )
        from skillsaw import RepositoryContext
        ctx = RepositoryContext(temp_dir)
        violations = opencode_color_rule().check(ctx)
        assert len(violations) == 0

    def test_all_presets_valid(self, temp_dir, opencode_color_rule):
        presets = ["primary", "secondary", "accent", "success", "warning", "error", "info"]
        for i, preset in enumerate(presets):
            _make_plugin_with_agent(
                temp_dir, f"plugin-{i}", "agent",
                f"name: agent\ncolor: {preset}",
            )
        from skillsaw import RepositoryContext
        ctx = RepositoryContext(temp_dir)
        violations = opencode_color_rule().check(ctx)
        assert len(violations) == 0

    def test_multiple_agents_mixed(self, temp_dir, opencode_color_rule):
        plugin_dir = temp_dir / "plugins" / "my-plugin"
        plugin_dir.mkdir(parents=True)
        claude_dir = plugin_dir / ".claude-plugin"
        claude_dir.mkdir()
        (claude_dir / "plugin.json").write_text(
            '{"name": "my-plugin", "version": "0.0.1", '
            '"description": "test", "author": "test"}'
        )
        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "good.md").write_text(
            '---\nname: good\ncolor: "#FF0000"\n---\n\nBody.\n'
        )
        (agents_dir / "bad.md").write_text(
            "---\nname: bad\ncolor: red\n---\n\nBody.\n"
        )
        from skillsaw import RepositoryContext
        ctx = RepositoryContext(temp_dir)
        violations = opencode_color_rule().check(ctx)
        assert len(violations) == 1
        assert "red" in violations[0].message
