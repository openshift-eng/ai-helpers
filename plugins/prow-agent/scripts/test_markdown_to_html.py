#!/usr/bin/env python3
"""Tests for markdown_to_html.py."""

import html
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser

import markdown_to_html

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "markdown_to_html.py")


def body(markdown):
    return "\n".join(markdown_to_html.render_body(markdown))


class _Collector(HTMLParser):
    """Collect what a browser would see: tags, attributes and the decoded <title> text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.attrs = []
        self.title = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend((tag, k, v) for k, v in attrs)
        self._in_title = tag == "title"

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and self.title is None:
            self.title = data


def parse(document):
    c = _Collector()
    c.feed(document)
    c.close()
    return c


def lens_view(document):
    """The document as the Prow html lens hands it to the browser.

    The lens replaces '"' with &quot; and puts the page into an iframe srcdoc
    attribute, so the browser decodes character references once more before it
    parses the page. html.unescape decodes at least as much as that step.
    """
    return html.unescape(document.replace('"', "&quot;"))


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def visible_text(document):
    t = _Text()
    t.feed(document)
    t.close()
    return "".join(t.parts)


class BlockTest(unittest.TestCase):
    def test_headings(self):
        self.assertEqual(body("# One\n### Three\n###### Six"), "<h1>One</h1>\n<h3>Three</h3>\n<h6>Six</h6>")
        self.assertEqual(body("#NoSpace"), "<p>#NoSpace</p>")

    def test_paragraphs_join_lines_and_split_on_blank_lines(self):
        self.assertEqual(body("first\nline\n\nsecond"), "<p>first line</p>\n<p>second</p>")

    def test_horizontal_rules(self):
        self.assertEqual(body("---\n***\n___"), "<hr>\n<hr>\n<hr>")

    def test_fenced_code_is_escaped_verbatim(self):
        self.assertEqual(
            body("```bash\n  echo <b> **x**\n```"),
            "<pre><code>  echo &lt;<!---->b&gt; **x**</code></pre>")

    def test_unterminated_fence_runs_to_end(self):
        self.assertEqual(body("```\na\nb"), "<pre><code>a\nb</code></pre>")

    def test_table(self):
        self.assertEqual(
            body("| A | B |\n|---|:--|\n| 1 | **2** |\n| 3 | `x` |"),
            "<table><thead><tr><th>A</th><th>B</th></tr></thead><tbody>"
            "<tr><td>1</td><td><strong>2</strong></td></tr>"
            "<tr><td>3</td><td><code>x</code></td></tr></tbody></table>")

    def test_table_escaped_pipe_is_a_literal_pipe(self):
        self.assertEqual(
            body("| A |\n|---|\n| a \\| b |"),
            "<table><thead><tr><th>A</th></tr></thead><tbody><tr><td>a | b</td></tr></tbody></table>")

    def test_pipe_line_without_separator_is_a_paragraph(self):
        self.assertEqual(body("| not a table |"), "<p>| not a table |</p>")

    def test_lists(self):
        self.assertEqual(body("- a\n* b\n+ c"), "<ul><li>a</li><li>b</li><li>c</li></ul>")
        self.assertEqual(body("1. a\n2) b"), "<ol><li>a</li><li>b</li></ol>")

    def test_list_continuation_lines(self):
        self.assertEqual(body("- a\n  continued\n- b"), "<ul><li>a continued</li><li>b</li></ul>")

    def test_blockquote(self):
        self.assertEqual(body("> one\n> **two**"), "<blockquote>one <strong>two</strong></blockquote>")


class InlineTest(unittest.TestCase):
    def test_emphasis_and_code(self):
        self.assertEqual(
            markdown_to_html.inline("**b** *e* `c *d*` a*b*c"),
            "<strong>b</strong> <em>e</em> <code>c *d*</code> a*b*c")

    def test_links(self):
        self.assertEqual(
            markdown_to_html.inline("[run](https://prow.example/view?a=1&b=2) http://h.example/x"),
            '<a href="https://prow.example/view?a=1&amp;b=2">run</a> '
            '<a href="http://h.example/x">http://h.example/x</a>')

    def test_link_text_keeps_code_spans(self):
        self.assertEqual(
            markdown_to_html.inline("[`id` x](https://e.example) **[b](https://b.example)**"),
            '<a href="https://e.example"><code>id</code> x</a> <strong><a href="https://b.example">b</a></strong>')

    def test_non_http_schemes_are_not_linked(self):
        for md in ("[x](javascript:alert(1))", "[x](data:text/html,hi)", "[x](file:///etc/passwd)",
                   "javascript:alert(1)", "[x](//evil.example)"):
            with self.subTest(md=md):
                self.assertNotIn("<a ", markdown_to_html.inline(md))

    def test_code_span_after_url_stays_out_of_href(self):
        self.assertEqual(
            markdown_to_html.inline('https://e.example/`x"`'),
            '<a href="https://e.example/">https://e.example/</a><code>x&quot;</code>')
        self.assertEqual(
            markdown_to_html.inline("https://a.example/[x](https://b.example)"),
            '<a href="https://a.example/">https://a.example/</a><a href="https://b.example">x</a>')

    def test_quote_in_url_cannot_break_out_of_href(self):
        out = markdown_to_html.inline('[x](https://e.example/a"onmouseover="alert(1))')
        self.assertIn('href="https://e.example/a%22onmouseover=%22alert(1"', out)
        attrs = parse(out).attrs
        self.assertEqual([k for _, k, _ in attrs], ["href"])


class EscapingTest(unittest.TestCase):
    HOSTILE = (
        "# <script>alert(1)</script>\n\n"
        "Text <img src=x onerror=alert(1)> & `<svg onload=alert(1)>`\n\n"
        "| <b>h</b> | x |\n|---|---|\n| <iframe src=javascript:alert(1)> | [a](https://e.example/\"><script>) |\n\n"
        "- <style>body{display:none}</style>\n\n"
        "> </blockquote><script>alert(2)</script>\n\n"
        "```\n</code></pre><script>alert(3)</script>\n```\n"
        "https://e.example/<script>alert(4)</script>\n\n"
        "See https://e.example/view/`x\" autofocus onfocus=\"alert(5)\" y=\"` here.\n"
        "[run](https://e.example/`a\" onmouseover=\"alert(6)\" b=\"`)\n"
    )

    def assert_only_renderer_markup(self, document):
        doc = parse(document)
        allowed = {"html", "head", "meta", "title", "style", "body", "h1", "p", "code", "table", "thead",
                   "tbody", "tr", "th", "td", "a", "ul", "li", "blockquote", "pre"}
        self.assertLessEqual(set(doc.tags), allowed)
        self.assertEqual(doc.tags.count("style"), 1)
        for tag, key, value in doc.attrs:
            if tag == "a":
                self.assertEqual(key, "href")
                self.assertRegex(value, r"^https?://")
            else:
                self.assertIn((tag, key), {("meta", "charset")})

    def test_no_markup_survives_from_input(self):
        self.assert_only_renderer_markup(markdown_to_html.render(self.HOSTILE, "t"))

    def test_no_markup_survives_in_the_prow_lens(self):
        self.assert_only_renderer_markup(lens_view(markdown_to_html.render(self.HOSTILE, "t")))

    def test_text_reads_the_same_directly_and_in_the_lens(self):
        md = "Expected <nil>, got `<b>x</b>` and </p> 3 < 4\n\n```\n<script>alert(3)</script>\n```\n"
        rendered = markdown_to_html.render(md, "t")
        for view in (rendered, lens_view(rendered)):
            with self.subTest(lens=view is not rendered):
                text = visible_text(view)
                self.assertIn("Expected <nil>, got <b>x</b> and </p> 3 < 4", text)
                self.assertIn("<script>alert(3)</script>", text)

    def test_every_escaped_less_than_is_followed_by_a_comment(self):
        rendered = markdown_to_html.render("<a> `<b>` [<c>](https://e.example) https://e.example/<d>", "t")
        # Attribute values are not parsed as markup, so hrefs keep the plain escape.
        text_html = re.sub(r'href="[^"]*"', "", rendered.split("<body>", 1)[1])
        self.assertNotRegex(text_html, r"&lt;(?!<!---->)")
        self.assertIn('href="https://e.example/&lt;d&gt;"', rendered)

    def test_placeholder_bytes_in_input_do_not_crash_or_reinject(self):
        md = "a \x000\x00 b \x011\x01 c `code` [l](https://e.example) \x7f\x1b[31m"
        out = body(md)
        self.assertEqual(
            out,
            '<p>a 0 b 1 c <code>code</code> <a href="https://e.example">l</a> [31m</p>')

    def test_control_bytes_removed_everywhere(self):
        out = markdown_to_html.render("# t\x01i\x00t\x08le\n\n```\nx\x00y\n```", "t")
        self.assertNotRegex(out, r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
        self.assertIn("<h1>title</h1>", out)


class TitleTest(unittest.TestCase):
    def test_title_is_inert_after_prow_style_decoding(self):
        # The Prow html lens decodes the <title> text and inserts it unescaped into the job page.
        for title in ("<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;",
                      "&amp;lt;img src=x onerror=alert(1)&amp;gt;", 'a"b\'c', "x\x00<\ny"):
            with self.subTest(title=title):
                decoded = parse(markdown_to_html.render("", title)).title
                self.assertIsNotNone(decoded)
                self.assertNotRegex(decoded, r"[<>&\"'\x00-\x1f]")

    def test_plain_titles_are_kept(self):
        self.assertEqual(markdown_to_html.safe_title("triage-duty-report-5.1-main.md"),
                         "triage-duty-report-5.1-main.md")
        self.assertEqual(markdown_to_html.safe_title("  Burst   tripwire\n"), "Burst tripwire")

    def test_empty_title_falls_back(self):
        self.assertEqual(markdown_to_html.safe_title("<&>"), markdown_to_html.DEFAULT_TITLE)
        self.assertEqual(markdown_to_html.safe_title(None), markdown_to_html.DEFAULT_TITLE)


class DocumentTest(unittest.TestCase):
    def test_document_shape_and_styling(self):
        out = markdown_to_html.render("hi", "Report")
        self.assertTrue(out.startswith('<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>Report</title><style>'))
        self.assertTrue(out.endswith("<p>hi</p>\n</body></html>\n"))
        self.assertIn("color-scheme:light dark", out)
        self.assertIn("@media (prefers-color-scheme:dark)", out)
        self.assertIn("html{background:var(--bg)}", out)
        self.assertNotIn("<script", out)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)

    def write(self, name, content):
        with open(self.path(name), "w", encoding="utf-8") as f:
            f.write(content)
        return self.path(name)

    def read(self, name):
        with open(self.path(name), encoding="utf-8") as f:
            return f.read()

    def test_renders_with_default_title(self):
        src = self.write("triage-duty-report-5.1-main.md", "# Report\n")
        r = self.run_cli(src, self.path("triage-summary-5.1-main.html"))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.read("triage-summary-5.1-main.html")
        self.assertIn("<title>triage-duty-report-5.1-main.md</title>", out)
        self.assertIn("<h1>Report</h1>", out)
        self.assertEqual(sorted(os.listdir(self.dir)), ["triage-duty-report-5.1-main.md", "triage-summary-5.1-main.html"])

    def test_explicit_title(self):
        src = self.write("in.md", "x")
        r = self.run_cli("--title", "Component Readiness <burst>", src, self.path("out.html"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("<title>Component Readiness burst</title>", self.read("out.html"))

    def test_non_utf8_input_is_replaced_not_fatal(self):
        with open(self.path("in.md"), "wb") as f:
            f.write(b"caf\xe9 <b>\n")
        r = self.run_cli(self.path("in.md"), self.path("out.html"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("<p>caf� &lt;<!---->b&gt;</p>", self.read("out.html"))

    def test_missing_input_fails_without_touching_output(self):
        self.write("out.html", "previous")
        r = self.run_cli(self.path("missing.md"), self.path("out.html"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("cannot read", r.stderr)
        self.assertEqual(self.read("out.html"), "previous")
        r = self.run_cli(self.path("missing.md"), self.path("new.html"))
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(self.path("new.html")))

    def test_unwritable_output_fails_cleanly(self):
        src = self.write("in.md", "x")
        r = self.run_cli(src, self.path("no-such-dir/out.html"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("cannot write", r.stderr)

    def test_usage_error(self):
        r = self.run_cli()
        self.assertEqual(r.returncode, 2)

    def test_output_mode_follows_umask(self):
        src = self.write("in.md", "x")
        r = subprocess.run(["sh", "-c", 'umask 022 && exec "$0" "$1" "$2" "$3"',
                            sys.executable, SCRIPT, src, self.path("out.html")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(stat.S_IMODE(os.stat(self.path("out.html")).st_mode), 0o644)
        self.assertEqual(sorted(os.listdir(self.dir)), ["in.md", "out.html"])


if __name__ == "__main__":
    unittest.main()
