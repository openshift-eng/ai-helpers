---
name: docs-convert-gdoc-md
description: Read a Google Docs document, Google Slides presentation, or Google Sheets spreadsheet and output as Markdown or CSV. Use this skill when asked to read, fetch, import, or convert a Google Doc, Google Slides, or Google Sheets URL.
model: claude-haiku-4-5@20251001
allowed-tools: Bash, Read, Write
---

# Convert Google Docs, Slides, or Sheets

Export Google content using the `gcloud` CLI for authentication:

- **Google Docs** → Markdown (`.md`)
- **Google Slides** → Markdown (`.md`) via PPTX with slide titles, bullet points, tables, and speaker notes
- **Google Sheets** → CSV (`.csv`)

## Prerequisites

- The [Red Hat Docs Agent Tools marketplace](https://aireilly.gitlab.cee.redhat.com/redhat-docs-agent-tools/install/) is installed
- `gcloud` CLI is installed
- User is authenticated via `gcloud auth login --enable-gdrive-access`
- `python-pptx` is installed for Slides export (`python3 -m pip install python-pptx`)

## Instructions

1. The user provides a Google Docs, Slides, or Sheets URL.
2. Run the conversion script with the URL as the argument.
3. Read the output file and present the content to the user.

### Run the script

The script is at `${CLAUDE_SKILL_DIR}/scripts/gdoc2md.py`.

Always quote the URL and output file arguments:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/gdoc2md.py [--comments] [--include-resolved] "<url>" ["<output_file>"]
```

- The script auto-detects the URL type:
  - `/document/d/` → Google Docs → Markdown
  - `/presentation/d/` → Google Slides → Markdown (via PPTX)
  - `/spreadsheets/d/` → Google Sheets → CSV
- If no output file is specified, it defaults to `<id>.md` or `<id>.csv`.

### Include Google Docs comments

Use `--comments` to pull comment threads from the document and insert them as Markdown footnotes:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/gdoc2md.py --comments "<google-doc-url>"
```

- Each comment with a highlighted text anchor becomes a footnote reference placed after the quoted text in the Markdown body.
- Comments without an anchor appear as footnotes at the end.
- Reply threads are included under the parent comment.
- By default, resolved comment threads are excluded. Add `--include-resolved` to include them.
- The `--comments` flag only applies to Google Docs. The script ignores it for Slides and Sheets.

### Error handling

- **401**: Authentication expired. Tell the user to run `gcloud auth login --enable-gdrive-access`.
- **403**: No permission. The user needs access to the document.
- **404**: Wrong URL or the document doesn't exist.
- **ImportError**: `python-pptx` not installed. Tell the user to run `python3 -m pip install python-pptx`.
