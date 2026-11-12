# prow-agent

Utilities for Claude Code and Codex sessions running inside Prow CI jobs.

## Session Metrics

Extracts cost, token, duration, and tool-usage metrics from Claude Code and
Codex sessions and writes an autodl JSON file for BigQuery ingestion.

### With agentic-ci (Preferred)

When using `agentic-ci run --backend local`, the OTEL collector is
managed automatically per invocation. Concatenate the per-run JSONL
files and pass them to `extract_metrics.py`:

```bash
EXTRACT_METRICS="/opt/ai-helpers/plugins/prow-agent/scripts/extract_metrics.py"
OTEL_LOG="${ARTIFACT_DIR}/claude-otel.jsonl"
PROMPT_ARGS=()

# Optional fallback when telemetry redacts the prompt. The file must contain
# the real initial harness prompt, not a placeholder.
if [[ -n "${INITIAL_PROMPT_FILE:-}" ]]; then
    PROMPT_ARGS=(--prompt-file "${INITIAL_PROMPT_FILE}")
fi

# agentic-ci writes OTEL JSONL to /tmp/agentic-ci-run.*/claude-otel.jsonl
# Concatenate after each invocation (see run_claude wrapper pattern)

python3 "${EXTRACT_METRICS}" "${OTEL_LOG}" \
    "${ARTIFACT_DIR}/claude-session-metrics-autodl.json" \
    "${PROMPT_ARGS[@]}"
```

Keep the full prompt file private, outside the artifact directory, and remove
it after extraction. When neither telemetry nor the `--stream-log` input provides
a usable prompt, the extractor intentionally copies the first 500 characters
into the exported `prompt` field, so the prompt must not contain secrets. Usable
telemetry and `--stream-log` prompts take precedence over this fallback.

See [docs/metrics-collection.md](docs/metrics-collection.md) for the
full design and BigQuery schema.

### Legacy Stream-JSON Parsing

The script also accepts a stream-json output log directly (auto-detected):

```bash
python3 "${EXTRACT_METRICS}" "${CLAUDE_OUTPUT_LOG}" \
    "${ARTIFACT_DIR}/claude-session-metrics-autodl.json"
```

For `--continue` workflows, run extraction once after the final
invocation. Each `result` message contains per-invocation totals; the
script sums across all result messages.

## Markdown Report to HTML

`markdown_to_html.py` renders a Markdown report as a standalone HTML page
(inline CSS, no scripts) so the Prow Spyglass `html` lens can show it on the
job page. It uses only the Python standard library.

```bash
MARKDOWN_TO_HTML="/opt/ai-helpers/plugins/prow-agent/scripts/markdown_to_html.py"

python3 "${MARKDOWN_TO_HTML}" [--title TITLE] report.md "${ARTIFACT_DIR}/report-summary.html"
```

- The title defaults to the input file name.
- Exit status is 0 on success, 1 when the input cannot be read or the output
  cannot be written, and 2 for usage errors. On failure no output file is
  created or replaced; writes go through a temporary file in the output
  directory.
- The html lens only picks up artifacts whose path matches one of its
  configured patterns (in openshift/release
  `core-services/prow/02_config/_config.yaml`, for example `.*-summary.*\.html`),
  so choose the output name accordingly.

### Supported Markdown

This is a deliberately small renderer for agent-written reports, not a full
Markdown engine:

- ATX headings (`#` to `######`), paragraphs, horizontal rules (`---`, `***`, `___`)
- `**bold**`, `*emphasis*` and `` `code` `` spans
- fenced code blocks (` ``` `)
- pipe tables with a header separator row; `\|` is a literal pipe in a cell
- flat `-`/`*`/`+` and `1.`/`1)` lists (continuation lines are joined), single-level `>` quotes
- `[text](https://...)` links and bare `http://`/`https://` URLs

Anything else is shown as escaped text. Nested lists, images, HTML passthrough,
setext headings and table column alignment are not supported.

### Safety

- All input text is HTML-escaped; raw HTML in the report is shown as text.
  The html lens embeds the page in an iframe `srcdoc` attribute without
  escaping `&`, so the browser decodes `&lt;` back to `<` before it parses the
  page. Every escaped `<` in text is therefore followed by an empty comment
  (`&lt;<!---->`), which is invisible when the file is opened directly and
  cannot start a tag after that extra decoding. Link targets keep the plain
  escape and never contain other markup, so they stay within their attribute.
- Only `http://` and `https://` targets become links; other schemes such as
  `javascript:` or `data:` stay plain text. A `"` in a URL is percent-encoded.
- C0 control characters other than tab, LF and CR, and DEL, are removed from
  the input.
- The page title is stripped of `<`, `>`, `&` and quotes. The html lens decodes
  the `<title>` text and inserts it into the job page without escaping it, so an
  escaped title alone would not be safe there.
- The page sets explicit light and dark colours (`prefers-color-scheme`), because
  the lens shows it in a transparent iframe over the job page's theme.

### Availability in CI images

The script ships in the `claude-ai-helpers` image at the path above once the
change is merged and the image is promoted by the ai-helpers `images`
postsubmit. Images built before that, or a step that replaces `/opt/ai-helpers`
with another ai-helpers checkout, may not contain it, so callers should check
that the file exists and treat rendering as best effort, keeping the Markdown
report as the primary artifact.
