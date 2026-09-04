import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.generate_site import generate_site, load_frontmatter, slugify  # noqa: E402


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def marketplace_fixture(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    plugin_dir = repo_root / "plugins" / "demo"
    write(
        plugin_dir / ".claude-plugin" / "plugin.json",
        json.dumps(
            {
                "name": "demo",
                "description": "Demo plugin metadata",
                "version": "1.2.3",
                "author": {"name": "github.com/openshift-eng"},
            }
        ),
    )
    write(
        plugin_dir / "commands" / "greet.md",
        """---
description: Greet a user
argument-hint: "[name]"
---

# Greet
""",
    )
    write(
        plugin_dir / "skills" / "investigate" / "SKILL.md",
        """---
name: investigate
description: Investigate a problem
---
""",
    )
    write(
        plugin_dir / "agents" / "reviewer.md",
        """---
name: reviewer
description: Review a proposed change
---
""",
    )

    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    write(
        marketplace_path,
        json.dumps(
            {
                "name": "test-marketplace",
                "owner": {"name": "test"},
                "metadata": {"description": "A test marketplace"},
                "plugins": [
                    {
                        "name": "demo",
                        "source": "./plugins/demo",
                        "description": "Demo plugin",
                        "version": "1.2.3",
                        "category": "tooling",
                        "keywords": ["example"],
                    },
                    {
                        "name": "external",
                        "source": {
                            "source": "github",
                            "repo": "example/external",
                            "path": "plugin",
                        },
                        "description": "Externally maintained",
                        "category": "shared-tools",
                    },
                ],
            }
        ),
    )
    return repo_root, marketplace_path


def test_generate_site_builds_navigation_and_content(tmp_path):
    repo_root, marketplace_path = marketplace_fixture(tmp_path)
    output_dir = repo_root / "site"
    write(output_dir / "docs" / "plugins" / "stale.md", "stale")

    plugins = generate_site(repo_root, marketplace_path, output_dir)

    assert [plugin.name for plugin in plugins] == ["demo", "external"]
    assert not (output_dir / "docs" / "plugins" / "stale.md").exists()
    assert (output_dir / "docs" / "index.md").exists()
    assert (output_dir / "docs" / "plugins" / "demo" / "commands" / "greet.md").exists()
    assert (
        output_dir / "docs" / "plugins" / "demo" / "skills" / "investigate.md"
    ).exists()
    assert (
        output_dir / "docs" / "plugins" / "demo" / "agents" / "reviewer.md"
    ).exists()

    plugin_page = (output_dir / "docs" / "plugins" / "demo" / "index.md").read_text()
    assert "/plugin install demo@ai-helpers" in plugin_page
    assert "Greet a user" in plugin_page
    external_page = (
        output_dir / "docs" / "plugins" / "external" / "index.md"
    ).read_text()
    assert "https://github.com/example/external/tree/main/plugin" in external_page
    assert "External plugin" in external_page

    config = (output_dir / "mkdocs.yml").read_text()
    parsed = yaml.safe_load(config.replace("!!python/name:", "# python/name:"))
    assert parsed["site_name"] == "AI Helpers Marketplace"
    assert "Plugins" in str(parsed["nav"])
    assert "plugins/demo/commands/greet.md" in config
    assert "categories/shared-tools.md" in config


def test_load_frontmatter_falls_back_for_plain_markdown(tmp_path):
    path = tmp_path / "plain.md"
    path.write_text("# Plain\n\nA useful summary.\n", encoding="utf-8")

    metadata, body = load_frontmatter(path)

    assert metadata == {}
    assert "A useful summary" in body


def test_slugify_handles_labels_safely():
    assert slugify("Team Tools / CI") == "team-tools-ci"


def test_generate_site_rejects_colliding_plugin_paths(tmp_path):
    repo_root, marketplace_path = marketplace_fixture(tmp_path)
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    marketplace["plugins"] = [
        {
            "name": name,
            "source": {"source": "github", "repo": f"example/{index}"},
            "category": "tooling",
        }
        for index, name in enumerate(("Foo Bar", "foo-bar"))
    ]
    marketplace_path.write_text(json.dumps(marketplace), encoding="utf-8")
    output_dir = repo_root / "site"

    with pytest.raises(ValueError, match="Generated path collision"):
        generate_site(repo_root, marketplace_path, output_dir)

    assert not (output_dir / "docs" / "index.md").exists()


@pytest.mark.parametrize("plugin_name", [".", ".."])
def test_generate_site_rejects_reserved_plugin_slugs(tmp_path, plugin_name):
    repo_root, marketplace_path = marketplace_fixture(tmp_path)
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    marketplace["plugins"][0]["name"] = plugin_name
    marketplace_path.write_text(json.dumps(marketplace), encoding="utf-8")
    output_dir = repo_root / "site"

    with pytest.raises(ValueError, match="is reserved"):
        generate_site(repo_root, marketplace_path, output_dir)

    assert not (output_dir / "docs" / "index.md").exists()


def test_generate_site_rejects_colliding_item_paths(tmp_path):
    repo_root, marketplace_path = marketplace_fixture(tmp_path)
    commands_dir = repo_root / "plugins" / "demo" / "commands"
    write(commands_dir / "one.md", "---\nname: Foo Bar\n---\n")
    write(commands_dir / "two.md", "---\nname: foo-bar\n---\n")

    with pytest.raises(ValueError, match="Generated path collision"):
        generate_site(repo_root, marketplace_path, repo_root / "site")


def test_generate_site_rejects_colliding_category_paths(tmp_path):
    repo_root, marketplace_path = marketplace_fixture(tmp_path)
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    marketplace["plugins"][0]["category"] = "Team Tools"
    marketplace["plugins"][1]["category"] = "team-tools"
    marketplace_path.write_text(json.dumps(marketplace), encoding="utf-8")

    with pytest.raises(ValueError, match="Generated path collision"):
        generate_site(repo_root, marketplace_path, repo_root / "site")
