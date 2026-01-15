---
name: Jira Wiki Markup Reference
description: JIRA Wiki Markup syntax for formatting issue descriptions
---

# Jira Wiki Markup Reference

This guide provides JIRA Wiki Markup formatting syntax for creating well-formatted issue descriptions and comments in Jira.

## Table of Contents

- [Text Formatting](#text-formatting)
  - [Headings](#headings)
  - [Text Effects](#text-effects)
- [Text Breaks](#text-breaks)
  - [Line Break](#line-break)
  - [Paragraph Break](#paragraph-break)
- [Lists](#lists)
  - [Bulleted Lists](#bulleted-lists)
  - [Alternative Bulleted Lists](#alternative-bulleted-lists)
  - [Numbered Lists](#numbered-lists)
  - [Mixed Lists](#mixed-lists)
- [Links](#links)
  - [External Links](#external-links)
  - [Internal Links](#internal-links-jira-issues)
  - [Section Links](#section-links)
  - [Attachment Links](#attachment-links)
  - [User Links](#user-links)
  - [Anchors](#anchors)
- [Images](#images)
  - [Basic Image](#basic-image)
  - [Remote Image](#remote-image)
  - [Thumbnail](#thumbnail)
  - [Image with Attributes](#image-with-attributes)
- [Tables](#tables)
  - [Basic Table](#basic-table)
  - [Table with Formatting](#table-with-formatting)
- [Code Blocks](#code-blocks)
  - [Inline Code](#inline-code)
  - [Code Block](#code-block)
  - [Code Block with Language](#code-block-with-language-highlighting)
  - [Preformatted Text](#preformatted-text-no-highlighting)
- [Panels and Quotes](#panels-and-quotes)
  - [Blockquote](#blockquote)
  - [Multi-line Quote](#multi-line-quote)
  - [Info Panel](#info-panel)
  - [Warning Panel](#warning-panel)
  - [Error Panel](#error-panel)
  - [Panel Macro](#panel-macro)
- [Colors](#colors)
  - [Text Color](#text-color)
- [Horizontal Rule and Dashes](#horizontal-rule-and-dashes)
  - [Horizontal Rule](#horizontal-rule)
  - [Dash Symbols](#dash-symbols)
- [Examples](#examples)
  - [User Story Template](#user-story-template)
  - [Bug Report Template](#bug-report-template)
  - [Epic Description Template](#epic-description-template)
- [Reference](#reference)

## Text Formatting

### Headings

```
h1. Heading 1
h2. Heading 2
h3. Heading 3
h4. Heading 4
h5. Heading 5
h6. Heading 6
```

### Text Effects

```
*bold text*
_italic text_
??citation??
-deleted-
+inserted+
^superscript^
~subscript~
{{monospace}}
```

## Text Breaks

### Line Break

```
\\
```

Creates a line break. Not often needed, most of the time Jira will handle line breaks automatically.

### Paragraph Break

Leave an empty line between paragraphs to create a new paragraph.

## Lists

### Bulleted Lists

```
* Item 1
* Item 2
** Nested item 2.1
** Nested item 2.2
* Item 3
```

Renders as:
- Item 1
- Item 2
  - Nested item 2.1
  - Nested item 2.2
- Item 3

### Alternative Bulleted Lists

```
- Item 1
- Item 2
- Item 3
```

Creates bulleted lists with a different bullet style (square bullets instead of round).

### Numbered Lists

```
# First item
# Second item
## Nested item 2.1
## Nested item 2.2
# Third item
```

### Mixed Lists

```
* Bullet item
*# Numbered sub-item
*# Another numbered sub-item
* Back to bullets
```

## Links

### External Links

```
[Link text|http://example.com]
```

### Internal Links (Jira Issues)

```
[PROJ-123]
```

Auto-links to the Jira issue PROJ-123.

### Section Links

```
[Link to section|#section-name]
```

### Attachment Links

```
[^attachment.ext]
```

Creates a link to a file attached to the current issue.

### User Links

```
[~username]
```

Creates a link to a user's profile page, with a user icon and the user's full name.

### Anchors

```
{anchor:anchorname}
```

Creates a bookmark anchor inside the page. You can then create links directly to that anchor using `[#anchorname]`.

## Images

### Basic Image

```
!image.gif!
```

Inserts an attached image into the page.

### Remote Image

```
!http://www.example.com/image.gif!
```

Inserts an image from a remote URL.

### Thumbnail

```
!image.jpg|thumbnail!
```

Inserts a thumbnail version of an attached image.

### Image with Attributes

```
!image.gif|align=right, vspace=4!
```

Inserts an image with specific HTML attributes as a comma-separated list.

## Tables

### Basic Table

```
||Header 1||Header 2||Header 3||
|Data 1|Data 2|Data 3|
|Data 4|Data 5|Data 6|
```

### Table with Formatting

```
||*Bold Header*||_Italic Header_||
|Content|More content|
|{color:red}Red text{color}|{color:green}Green text{color}|
```

## Code Blocks

### Inline Code

```
This is {{inline code}} in text.
```

### Code Block

```
{code}
function helloWorld() {
  console.log("Hello, World!");
}
{code}
```

### Code Block with Language Highlighting

```
{code:python}
def hello_world():
    print("Hello, World!")
{code}
```

Supported languages: java, python, javascript, bash, go, rust, sql, yaml, json, xml, etc.

You can also add additional parameters:

```
{code:title=MyFile.java|borderStyle=solid}
// Code here
{code}
```

### Preformatted Text (No Highlighting)

```
{noformat}
preformatted text
*no* _formatting_ is applied here
{noformat}
```

Creates a preformatted block of text with no syntax highlighting. All wiki markup is ignored inside `{noformat}` blocks.

## Panels and Quotes

### Blockquote

```
bq. This is a blockquote
```

Creates a single-line blockquote.

### Multi-line Quote

```
{quote}
This is a longer quote
that spans multiple lines.
{quote}
```

Creates a multi-line blockquote block.

### Info Panel

```
{info}
This is an informational message.
{info}
```

### Warning Panel

```
{warning}
This is a warning message.
{warning}
```

### Error Panel

```
{error}
This is an error message.
{error}
```

**Note:** The `{info}`, `{warning}`, and `{error}` panel macros may not be available in all Jira configurations. These macros are commonly available in Confluence but may have limited support in Jira. If these don't work, use the `{panel}` macro with custom styling instead.

### Panel Macro

```
{panel:title=My Title|borderStyle=solid|borderColor=#ccc|bgColor=#FFFFCE}
Custom panel content here
{panel}
```

Creates a fully customizable panel. Available parameters:
- `title` - Panel title
- `borderStyle` - Border style (solid, dashed, etc.)
- `borderColor` - Border color (hex or color name)
- `borderWidth` - Border width
- `bgColor` - Background color
- `titleBGColor` - Title background color

## Colors

### Text Color

```
{color:red}Red text{color}
{color:green}Green text{color}
{color:blue}Blue text{color}
{color:#FF0000}Custom hex color{color}
```

Supported colors: red, green, blue, yellow, orange, purple, brown, gray, black, white, and hex colors (#RRGGBB)

## Horizontal Rule and Dashes

### Horizontal Rule

```
----
```

Creates a horizontal line separator. Note: **Four dashes** are required.

### Dash Symbols

```
---
--
```

- `---` (three dashes) produces an em-dash (—) symbol
- `--` (two dashes) produces an en-dash (–) symbol

## Examples

### User Story Template

```
As a {{cluster admin}}, I want to {{configure autoscaling}}, so that {{I can handle traffic spikes}}.

h2. Acceptance Criteria

* Test that node pools scale up when CPU exceeds 80%
* Test that node pools scale down when CPU drops below 30%
* Test that scaling respects configured min/max node limits

h2. Additional Context

This feature integrates with the existing monitoring infrastructure introduced in [PROJ-100].

h3. Dependencies

* [PROJ-99] - Monitoring infrastructure
* Coordination with Platform team for API access

h3. Out of Scope

* Custom metrics-based scaling (future story)
```

### Bug Report Template

```
h2. Description

The {{API server}} returns a {{500 error}} when creating namespaces with {{special characters}} in the name.

h2. Steps to Reproduce

# Create a namespace with special characters: {{kubectl create namespace test-@-ns}}
# Observe the API server response
# Check the API server logs for details

h2. Actual Result

{{HTTP 500 Internal Server Error}} returned. API logs show {{panic: regex compilation failed}}.

h2. Expected Result

Namespace should be created successfully, or a {{400 Bad Request}} should be returned with clear validation error message.

h2. Additional Info

* OpenShift Version: 4.21
* Affected Component: {{Kubernetes API Server}}
* First reported in: Version 4.20

{code}
Error from server (InternalError): error when creating "manifest.yaml": Internal error occurred: failed to validate object against schema: regex compilation failed
{code}
```

### Epic Description Template

```
h2. Use Case / Context

Implement comprehensive monitoring and observability for {{GCP-hosted control planes}} across multiple {{GKE clusters}}, enabling operators to detect and respond to issues proactively.

h2. Current State

* Limited visibility into control plane metrics
* Manual troubleshooting process
* Slow mean time to resolution (MTTR)

h2. Desired State

* Real-time metrics collection from control plane pods
* Centralized metrics aggregation and storage
* Pre-built dashboards for cluster health monitoring
* Alerting framework for critical metrics

h2. Scope

*This Epic covers:*
* Metrics collection from control plane pods
* Central metrics aggregation and storage
* Dashboards for monitoring cluster health
* Alerting framework for critical metrics
* Log aggregation and analysis

*Out of Scope:*
* Custom application metrics (separate Epic)
* Alert routing to external systems (future)

h2. Acceptance Criteria

* Test that metrics are collected from all control plane pods
* Test that metrics are available within 30 seconds of generation
* Test that dashboards accurately reflect cluster state
* Test that alerts fire within 2 minutes of anomaly detection
```

## Reference

- [Atlassian JIRA Wiki Markup Documentation](https://confluence.atlassian.com/confcloud/jira-wiki-markup-821470675.html)
- [Text Formatting Notation Help](https://jira.atlassian.com/secure/RenderMarkupHelp.jspa?helpKey=jira.markup.help.heading)
