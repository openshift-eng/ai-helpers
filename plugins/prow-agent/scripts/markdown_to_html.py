#!/usr/bin/env python3
"""Render a Markdown report as a standalone HTML page for Prow artifacts.

Converts the small Markdown subset that CI agents write in their reports into a
self-contained HTML page (inline CSS, no scripts, no network access) that the
Prow Spyglass ``html`` lens can show on the job page. Uses only the Python
standard library, so it runs in any image with ``python3``.

This is a deliberately small renderer, not a full Markdown engine. Supported:

- ATX headings (# to ######), paragraphs, horizontal rules
- **bold**, *emphasis* and `code` spans
- fenced code blocks (```)
- pipe tables with a header separator row (an escaped \\| is a literal pipe)
- flat -/*/+ and 1./1) lists, single-level > quotes
- [text](https://...) links and bare http(s):// URLs

All text is HTML-escaped, and every escaped "<" is followed by an empty HTML
comment so that it stays text even where the page is embedded in an iframe
srcdoc attribute, as the Prow html lens does. Only http:// and https:// targets
become links; any other scheme (javascript:, data:, ...) stays plain text.
Control characters other than tab, LF and CR are removed from the input, and
the page title is stripped of <, >, & and quotes.

Usage:
    python3 markdown_to_html.py [--title TITLE] INPUT.md OUTPUT.html

The title defaults to the input file name. Exit status is 0 on success, 1 when
the input cannot be read or the output cannot be written (no output file is
created or replaced then), and 2 for usage errors.
"""

import argparse
import html
import os
import re
import sys
import tempfile

# C0 controls other than tab, LF and CR, plus DEL. They are not valid in HTML
# text, and NUL/SOH are used below as internal placeholder delimiters, so they
# are removed from the input before rendering.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Characters removed from the page title. The Prow html lens reads the <title>
# text with an HTML tokenizer, which decodes entities, and inserts the result
# into the job page without escaping it again. Escaping alone is therefore not
# enough: "&lt;script&gt;" would come back as live markup. Without <, > and &
# no markup or entity can be formed; quotes are dropped as well.
_TITLE_UNSAFE = re.compile(r"[<>&\"'\x00-\x1f\x7f]")

# The Prow html lens puts the page into an iframe srcdoc="..." attribute and
# only replaces '"' with &quot;, so the browser decodes character references
# once before parsing the page: an escaped "&lt;" in the text becomes a literal
# "<" again and could start a tag. Each escaped "<" in text is therefore
# followed by an empty comment. Opened directly, "&lt;<!---->" shows "<"; in the
# lens it decodes to "<<!---->", where the first "<" cannot start a tag either.
_SAFE_LT = "&lt;<!---->"

DEFAULT_TITLE = "Report"

# Explicit colours for both schemes: Prow shows the page in a transparent
# iframe, so without a background the job page's own (often dark) theme shows
# through and dark text becomes unreadable.
CSS = (
    ":root{color-scheme:light dark;--fg:#1f2328;--bg:#ffffff;--muted:#57606a;--line:#d0d7de;--soft:#f6f8fa;--link:#0969da}"
    "@media (prefers-color-scheme:dark){:root{--fg:#e6edf3;--bg:#0d1117;--muted:#9198a1;--line:#3d444d;--soft:#161b22;--link:#4493f8}}"
    "html{background:var(--bg)}body{background:var(--bg);color:var(--fg);font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;"
    "font-size:14px;line-height:1.5;margin:0;padding:16px;overflow-wrap:anywhere}"
    "h1,h2,h3,h4,h5,h6{color:var(--fg);margin:20px 0 8px;line-height:1.25}h1{font-size:1.6em}h2{font-size:1.35em;"
    "border-bottom:1px solid var(--line);padding-bottom:4px}h3{font-size:1.15em}a{color:var(--link)}"
    "table{border-collapse:collapse;margin:8px 0;display:block;max-width:100%;overflow-x:auto}"
    "th,td{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}th{background:var(--soft)}"
    "tbody tr:nth-child(even){background:var(--soft)}"
    "code{background:var(--soft);color:var(--fg);padding:1px 4px;border-radius:4px;font-size:90%}"
    "pre{background:var(--soft);padding:8px;overflow:auto}pre code{padding:0}"
    "hr{border:0;border-top:1px solid var(--line);margin:16px 0}"
    "blockquote{border-left:4px solid var(--line);margin:0;padding:0 12px;color:var(--muted)}"
)


def inert(escaped):
    """Make HTML-escaped text stay text after one more round of entity decoding."""
    return escaped.replace("&lt;", _SAFE_LT)


def safe_title(title):
    """Return a page title that stays inert after Prow's html lens decodes it."""
    cleaned = " ".join(_TITLE_UNSAFE.sub(" ", title or "").split())
    return cleaned or DEFAULT_TITLE


def inline(t):
    """Render inline Markdown (code, links, bold, emphasis) in escaped text."""
    codes = []

    def keep(m):
        codes.append("<code>%s</code>" % inert(html.escape(m.group(1))))
        return "\x00%d\x00" % (len(codes) - 1)

    t = re.sub(r"`([^`]+)`", keep, t)
    t = html.escape(t, quote=False)
    links = []

    def link(href, text):
        links.append('<a href="%s">%s</a>' % (href.replace('"', "%22"), inert(text)))
        return "\x01%d\x01" % (len(links) - 1)

    # Link targets stop at the placeholder bytes, so a code span or link next to
    # a URL can never end up inside an href.
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s\x00\x01]+)\)", lambda m: link(m.group(2), m.group(1)), t)
    t = re.sub(r"https?://[^\s<)\]\x00\x01]+", lambda m: link(m.group(0), m.group(0)), t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<em>\1</em>", t)
    t = inert(t)
    t = re.sub(r"\x01(\d+)\x01", lambda m: links[int(m.group(1))], t)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], t)


def cells(row):
    """Split a pipe-table row into cells; an escaped pipe stays in its cell."""
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", row)]


def render_body(text):
    """Render the Markdown text as a sequence of HTML block elements."""
    lines = _CONTROL_CHARS.sub("", text).splitlines()
    body, para, i = [], [], 0

    def flush():
        if para:
            body.append("<p>%s</p>" % inline(" ".join(para)))
            para.clear()

    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("```"):
            flush()
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            body.append("<pre><code>%s</code></pre>" % inert(html.escape("\n".join(code))))
        elif not s:
            flush()
        elif re.match(r"^#{1,6}\s", s):
            flush()
            n = len(s) - len(s.lstrip("#"))
            body.append("<h%d>%s</h%d>" % (n, inline(s[n:].strip()), n))
        elif re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            flush()
            body.append("<hr>")
        elif s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|?\s*:?-{2,}", lines[i + 1].strip()):
            flush()
            head = cells(s)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            body.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (
                "".join("<th>%s</th>" % inline(c) for c in head),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in rows)))
            continue
        elif re.match(r"^([-*+]|\d+[.)])\s", s):
            flush()
            tag = "ol" if s[0].isdigit() else "ul"
            items = []
            while i < len(lines) and lines[i].strip():
                t = lines[i].strip()
                m = re.match(r"^([-*+]|\d+[.)])\s+(.*)$", t)
                if m:
                    items.append(m.group(2))
                elif items:
                    items[-1] += " " + t
                else:
                    break
                i += 1
            body.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % inline(x) for x in items), tag))
            continue
        elif s.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            body.append("<blockquote>%s</blockquote>" % inline(" ".join(quote)))
            continue
        else:
            para.append(s)
        i += 1
    flush()
    return body


def render(text, title=DEFAULT_TITLE):
    """Return a complete HTML document for the Markdown text."""
    return (
        '<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>%s</title><style>%s</style></head><body>\n%s\n</body></html>\n'
        % (html.escape(safe_title(title)), CSS, "\n".join(render_body(text)))
    )


def write_atomic(path, content):
    """Write content to path via a temporary file in the same directory."""
    directory = os.path.dirname(os.path.abspath(path))
    umask = os.umask(0)
    os.umask(umask)
    fd, tmp = tempfile.mkstemp(prefix=".markdown-to-html-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        # mkstemp creates the file 0600; give it the mode a plain open() would.
        os.chmod(tmp, 0o666 & ~umask)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Render a Markdown report (a small, documented subset) as a standalone HTML page.")
    parser.add_argument("input", help="Markdown file to render")
    parser.add_argument("output", help="HTML file to write (replaced atomically)")
    parser.add_argument("--title", help="page title (default: the input file name)")
    args = parser.parse_args(argv)

    try:
        with open(args.input, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        print("markdown_to_html: cannot read %s: %s" % (args.input, e.strerror or e), file=sys.stderr)
        return 1

    title = args.title if args.title is not None else os.path.basename(args.input)
    try:
        write_atomic(args.output, render(text, title))
    except OSError as e:
        print("markdown_to_html: cannot write %s: %s" % (args.output, e.strerror or e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
