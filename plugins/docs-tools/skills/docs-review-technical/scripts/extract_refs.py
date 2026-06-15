#!/usr/bin/env python3
"""Extract technical references from documentation files.

Parses AsciiDoc and Markdown files to identify commands, code blocks,
API references, configuration keys, and file paths. Outputs structured
JSON for use by review agents.

Usage:
    python3 extract_refs.py <doc files...> [--output refs.json]
"""

import argparse
import json
import logging
import re
from pathlib import Path

log = logging.getLogger("extract_refs")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKIP_FUNCTIONS = frozenset(
    "if for while print return len map set get new int str list dict type "
    "var let const def end do nil true false else case break next puts echo "
    "test eval".split()
)

# Regex patterns for AsciiDoc / Markdown parsing
RE_SOURCE_BLOCK = re.compile(r"^\[source(?:,\s*([a-z0-9+\-_]+))?(?:,\s*(.+))?\]\s*$", re.I)
RE_CODE_FENCE = re.compile(r"^```\s*([a-z0-9+\-_]+)?\s*$", re.I)
RE_CODE_DELIM = re.compile(r"^-{4,}\s*$")
RE_LITERAL_DELIM = re.compile(r"^\.{4,}\s*$")
RE_LISTING_BLOCK = re.compile(r"^\[listing\]\s*$", re.I)
RE_HEADING_ADOC = re.compile(r"^(=+)\s+(.+)$")
RE_HEADING_MD = re.compile(r"^(#{1,6})\s+(.+)$")
RE_BLOCK_TITLE = re.compile(r"^\.([A-Za-z][^\n]*?)\s*$")
RE_COMMAND_LINE = re.compile(r"^\$\s+(.+)$")
RE_COMMAND_LINE_CODE = re.compile(r"^\$\s+(.+)$")
RE_INLINE_CODE_PATH = re.compile(r"`([a-zA-Z0-9_\-.\/]+\.[a-z]{2,})`")
RE_FUNCTION_CALL = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
RE_CLASS_DEF = re.compile(r"\b(?:class|interface|struct)\s+([A-Z][a-zA-Z0-9_]*)")
RE_API_ENDPOINT = re.compile(r"(?:GET|POST|PUT|PATCH|DELETE)\s+(/[a-z0-9/_\-{}]+)")
RE_COMMENT_LINE = re.compile(r"^//($|[^/].*)$")
RE_COMMENT_BLOCK = re.compile(r"^/{4,}\s*$")


class Extractor:
    """Extract technical references from AsciiDoc / Markdown files."""

    def __init__(self):
        self.refs = {
            "commands": [],
            "code_blocks": [],
            "apis": [],
            "configs": [],
            "file_paths": [],
        }

    def extract_files(self, paths: list[str]) -> dict:
        for p in paths:
            path = Path(p)
            if path.is_dir():
                for f in sorted(path.rglob("*")):
                    if f.suffix in (".adoc", ".md"):
                        self._extract_file(f)
            elif path.is_file():
                self._extract_file(path)
            else:
                log.warning("Not found: %s", p)
        return self.refs

    def _extract_file(self, path: Path):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            log.warning("Cannot read %s: %s", path, exc)
            return

        fpath = str(path)
        in_code = False
        code_delim = None
        block = None
        heading = None
        block_title = None
        in_comment = False
        comment_delim = None
        skip_next = False

        for idx, line in enumerate(lines):
            line_num = idx + 1

            if skip_next:
                skip_next = False
                continue

            # Comment blocks
            if RE_COMMENT_BLOCK.match(line):
                if in_comment and line == comment_delim:
                    in_comment = False
                    comment_delim = None
                else:
                    in_comment = True
                    comment_delim = line
                continue
            if in_comment or RE_COMMENT_LINE.match(line):
                continue

            # Headings (outside code blocks)
            if not in_code:
                m = RE_HEADING_ADOC.match(line) or RE_HEADING_MD.match(line)
                if m:
                    heading = m.group(2).strip()
                    continue

            # Block titles
            if RE_BLOCK_TITLE.match(line) and not in_code:
                block_title = line[1:].strip()
                continue

            # Code block start
            if not in_code:
                lang = None
                delim = None

                m = RE_SOURCE_BLOCK.match(line)
                if m:
                    lang = m.group(1) or "text"
                    if idx + 1 < len(lines):
                        nxt = lines[idx + 1]
                        if RE_CODE_DELIM.match(nxt) or RE_LITERAL_DELIM.match(nxt):
                            delim = nxt
                            skip_next = True
                    in_code = True
                    code_delim = delim
                    block = {
                        "file": fpath,
                        "line": line_num,
                        "content_start_line": line_num + (2 if skip_next else 1),
                        "language": lang,
                        "content": [],
                        "context": block_title or heading,
                    }
                    continue

                if RE_LISTING_BLOCK.match(line):
                    lang = "text"
                    if idx + 1 < len(lines):
                        nxt = lines[idx + 1]
                        if RE_CODE_DELIM.match(nxt) or RE_LITERAL_DELIM.match(nxt):
                            delim = nxt
                            skip_next = True
                    in_code = True
                    code_delim = delim
                    block = {
                        "file": fpath,
                        "line": line_num,
                        "content_start_line": line_num + (2 if skip_next else 1),
                        "language": lang,
                        "content": [],
                        "context": block_title or heading,
                    }
                    continue

                m = RE_CODE_FENCE.match(line)
                if m:
                    lang = m.group(1) or "text"
                    in_code = True
                    code_delim = "```"
                    block = {
                        "file": fpath,
                        "line": line_num,
                        "content_start_line": line_num + 1,
                        "language": lang,
                        "content": [],
                        "context": block_title or heading,
                    }
                    continue

                if RE_CODE_DELIM.match(line):
                    in_code = True
                    code_delim = line
                    block = {
                        "file": fpath,
                        "line": line_num,
                        "content_start_line": line_num + 1,
                        "language": "text",
                        "content": [],
                        "context": block_title or heading,
                    }
                    continue
            else:
                # Inside code block — check for end
                is_end = False
                if code_delim == "```" and line == "```":
                    is_end = True
                elif code_delim and line == code_delim:
                    is_end = True
                elif code_delim is None:
                    if (
                        not line.strip()
                        or RE_SOURCE_BLOCK.match(line)
                        or RE_LISTING_BLOCK.match(line)
                        or RE_HEADING_ADOC.match(line)
                    ):
                        is_end = True

                if is_end and block is not None:
                    block["content"] = "\n".join(block["content"])
                    self.refs["code_blocks"].append(block)
                    self._extract_from_code_block(block, fpath)
                    in_code = False
                    code_delim = None
                    block = None
                    block_title = None
                elif block is not None:
                    block["content"].append(line)
                continue

            # Outside code block — inline references
            # A block title only applies to the immediately following block.
            # If we reach here, the line is not a code block opener, so clear it.
            block_title = None

            # Commands ($ command)
            m = RE_COMMAND_LINE.match(line)
            if m:
                self.refs["commands"].append(
                    {
                        "file": fpath,
                        "line": line_num,
                        "command": m.group(1).strip(),
                        "context": block_title or heading,
                    }
                )

            # Inline code paths
            for m in RE_INLINE_CODE_PATH.finditer(line):
                self.refs["file_paths"].append(
                    {
                        "file": fpath,
                        "line": line_num,
                        "path": m.group(1),
                        "context": heading,
                    }
                )

            # API endpoints
            m = RE_API_ENDPOINT.search(line)
            if m:
                self.refs["apis"].append(
                    {
                        "file": fpath,
                        "line": line_num,
                        "type": "endpoint",
                        "name": m.group(1),
                        "context": heading,
                    }
                )

        # Handle unclosed block
        if in_code and block:
            block["content"] = "\n".join(block["content"])
            self.refs["code_blocks"].append(block)
            self._extract_from_code_block(block, fpath)
            log.warning("Unclosed code block in %s at line %d", fpath, block["line"])

    def _extract_from_code_block(self, block: dict, fpath: str):
        content = block["content"]
        lang = block.get("language", "text")
        ctx = block.get("context")
        content_start = block.get("content_start_line", block["line"])
        content_lines = content.splitlines()

        # Commands from code block lines
        for offset, cline in enumerate(content_lines):
            m = RE_COMMAND_LINE_CODE.match(cline.strip())
            if m:
                prompt = "root" if cline.lstrip().startswith("#") else "user"
                self.refs["commands"].append(
                    {
                        "file": fpath,
                        "line": content_start + offset,
                        "command": m.group(1).strip(),
                        "prompt_type": prompt,
                        "context": ctx,
                    }
                )

        # Function calls
        for m in RE_FUNCTION_CALL.finditer(content):
            name = m.group(1)
            if len(name) < 3 or name.lower() in SKIP_FUNCTIONS:
                continue
            hit_offset = content[: m.start()].count("\n")
            self.refs["apis"].append(
                {
                    "file": fpath,
                    "line": content_start + hit_offset,
                    "type": "function",
                    "name": name,
                    "language": lang,
                    "context": ctx,
                }
            )

        # Class definitions
        for m in RE_CLASS_DEF.finditer(content):
            hit_offset = content[: m.start()].count("\n")
            self.refs["apis"].append(
                {
                    "file": fpath,
                    "line": content_start + hit_offset,
                    "type": "class",
                    "name": m.group(1),
                    "language": lang,
                    "context": ctx,
                }
            )

        # Config keys from YAML/JSON/TOML
        if lang.lower() in ("yaml", "yml", "json", "toml"):
            self._extract_config_keys(content, fpath, content_start, lang, ctx)

    def _extract_config_keys(self, content: str, fpath: str, line_num: int, fmt: str, ctx):
        keys = []
        fl = fmt.lower()
        if fl in ("yaml", "yml"):
            keys = [
                m.group(1) for m in re.finditer(r"^\s*([a-zA-Z_][a-zA-Z0-9_-]*):", content, re.M)
            ]
        elif fl == "json":
            keys = [m.group(1) for m in re.finditer(r'"([a-zA-Z_][a-zA-Z0-9_-]*)"\s*:', content)]
        elif fl == "toml":
            keys = [
                m.group(1) for m in re.finditer(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*=", content, re.M)
            ]

        keys = list(dict.fromkeys(keys))  # dedupe preserving order
        if keys:
            self.refs["configs"].append(
                {
                    "file": fpath,
                    "line": line_num,
                    "format": fmt,
                    "keys": keys,
                    "context": ctx,
                }
            )


def main():
    parser = argparse.ArgumentParser(
        description="Extract technical references from documentation files.",
    )
    parser.add_argument("files", nargs="+", help="AsciiDoc/Markdown files or directories")
    parser.add_argument("-o", "--output", help="Write JSON to file instead of stdout")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    extractor = Extractor()
    refs = extractor.extract_files(args.files)
    output = {
        "summary": {k: len(v) for k, v in refs.items()},
        "references": refs,
    }
    text = json.dumps(output, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Extracted references to {args.output}")
        for k, v in refs.items():
            print(f"  {k}: {len(v)}")
    else:
        print(text)


if __name__ == "__main__":
    main()
