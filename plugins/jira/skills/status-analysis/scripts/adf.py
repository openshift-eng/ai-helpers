"""Helpers for consuming Atlassian Document Format values."""

from typing import Any


def adf_to_text(node: Any) -> str:
    """Return a readable plain-text rendering of an ADF document or text value."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return str(node)

    parts: list[str] = []
    node_type = node.get("type")
    if node_type == "text":
        text = node.get("text", "")
        for mark in node.get("marks", []):
            if mark.get("type") == "link":
                href = mark.get("attrs", {}).get("href", "")
                if href and href != text:
                    text = f"{text} ({href})"
        parts.append(text)
    elif node_type in ("inlineCard", "blockCard", "embedCard"):
        url = node.get("attrs", {}).get("url", "")
        if url:
            parts.append(url)

    for child in node.get("content", []):
        parts.append(adf_to_text(child))

    separator = "\n" if node_type in {
        "doc", "paragraph", "heading", "bulletList", "orderedList", "listItem", "blockquote"
    } else ""
    return separator.join(parts)
