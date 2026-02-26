---
page_meta:
  title: CCFM Example Files - Complete Element Reference
  space: PE
  author: "Platform Team"
  labels:
    - ccfm
    - reference
    - example
  attachments:
    - path: CCFM.png
      alt: "CCFM Project Logo.png"
      width: max

deploy_config:
  ci_banner: true                         # Show CI banner (default: true)
  ci_banner_text: "🤖 Custom banner text" # Optional
  include_page_metadata: true             # Shows expand with metadata
  page_status: "current"                  # "current" or "draft" (default: "current")
  deploy_page: true                       # Deploy this page (default: true)
---

# CCFM Complete Element Reference

This page exercises every element defined in the CCFM specification. It serves as both a
visual reference for what CCFM produces in Confluence, and a validation document for the
converter. If everything on this page renders correctly, the converter is working.

---

## Headings

All six heading levels are supported.

## H2 — Major section heading

### H3 — Subsection heading

#### H4 — Minor heading

##### H5 — Small heading

###### H6 — Smallest heading

Back to normal paragraph text after the heading run.

---

## Paragraphs and line breaks

This is the first paragraph. It is a plain block of text with no special formatting.
Multiple lines in the source file that are not separated by a blank line are part of the
same paragraph.

This is the second paragraph, separated from the first by a blank line.

This paragraph contains a hard break produced by a trailing backslash.\
This is the second line of the same paragraph, not a new paragraph.

This paragraph contains a hard break produced by two trailing spaces.
This is the second line, same paragraph.

---

## Emphasis and inline marks

Plain text for contrast, then formatted variants:

**Bold text using double asterisks.**

*Italic text using single asterisks.*

*Italic text using underscores.*

***Bold and italic combined using triple asterisks.***

~~Strikethrough text using double tildes.~~

++Underlined text using double plus signs. Use sparingly.++

Superscript: E = mc^2^ and the answer is 2^10^ = 1024.

Subscript: The formula for water is H~2~O and CO~2~ is carbon dioxide.

Combined: You can have **bold with *italic* nested inside it** and ~~struck ~~
~~through~~ text that wraps~~ lines.

All marks on a single line: **bold**, *italic*, `code`, ~~strike~~, ++underline++,
x^2^, H~2~O.

---

## Inline code

Run the `deploy` command to publish pages to Confluence.

Set the `CONFLUENCE_TOKEN` environment variable before running any deploy commands.

The function `convert_markdown_to_adf(text)` returns a Python dict representing the ADF document.

---

## Links

### External links

Read the [Atlassian Developer Documentation](https://developer.atlassian.com/) for full
ADF schema details.

The [CommonMark specification](https://spec.commonmark.org/) underpins CCFM's base syntax.

### Confluence page links

Link to other pages in Confluence using angle bracket syntax:

This is an internal page link to My Team [CCFM Example - My Team](<CCFM Example - My Team>).

And another one for My App [CCFM Example - My App](<CCFM Example - My App>).

---

## Images

External image:

![Atlassian logo — coloured gradient](https://wac-cdn.atlassian.com/misc-assets/adg4-nav/AtlassianHeaderLogo.svg)

Internal image:

![CCFM Logo](CCFM.png)

---

## Horizontal rules

Use three or more hyphens on their own line to produce a horizontal divider.

Above this line is a paragraph. Below is the rule.

---

Above is the rule. Below is another paragraph.

---

## Lists

### Unordered list

- First item
- Second item with **bold text** inside
- Third item with `inline code` inside
- Fourth item with an [external link](https://example.com) inside

### Ordered list

1. Clone the repository
2. Install dependencies with `pip install -r requirements.txt`
3. Configure credentials in your environment
4. Run the deploy script

### Nested unordered list

- Top-level item one
  - Nested item A
  - Nested item B
    - Deeply nested item i
    - Deeply nested item ii
  - Nested item C
- Top-level item two
- Top-level item three

### Nested ordered list

1. First top-level step
   1. Sub-step one-one
   2. Sub-step one-two
2. Second top-level step
   1. Sub-step two-one
3. Third top-level step

### Mixed nested list

- Unordered top level
  1. Ordered child step one
  2. Ordered child step two
- Another unordered item
  - Unordered child

---

## Task lists

Simple task list with checked and unchecked items:

- [ ] Unchecked task one
- [x] Checked task (completed)
- [ ] Unchecked task two
- [x] Another completed task

Task list with inline formatting:

- [ ] Review **pull request #456**
- [x] Deploy to `staging` environment :rocket:
- [ ] Notify engineering team via ::Slack::blue::
- [x] Verify deployment on @date:2026-02-17

> **Note:** Task items in ADF contain inline content only. Nested task lists and
> multi-paragraph task items are not currently supported by the converter.

---

## Code blocks

### Python

```python
def convert_markdown_to_adf(markdown_text: str) -> dict:
    """
    Convert a CCFM markdown string to an ADF document dict.
    Frontmatter must be stripped before calling this function.
    """
    lines = markdown_text.splitlines()
    content = []
    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            content.append(heading(level, parse_inline(text)))
    return doc(content)
```

### JavaScript

```javascript
async function deployPage(domain, space, title, adfBody) {
  const response = await fetch(`https://${domain}/wiki/api/v2/pages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Basic ${btoa(`${email}:${token}`)}`,
    },
    body: JSON.stringify({
      spaceId: space,
      title: title,
      body: {
        representation: 'atlas_doc_format',
        value: JSON.stringify(adfBody),
      },
    }),
  });
  return response.json();
}
```

### Bash

```bash
#!/bin/bash
set -euo pipefail

python src/deploy.py \
    --domain "${CONFLUENCE_DOMAIN}" \
    --email "${CONFLUENCE_EMAIL}" \
    --token "${CONFLUENCE_TOKEN}" \
    --space "${CONFLUENCE_SPACE}" \
    --file docs/my-page.md

echo "Deployment complete."
```

### YAML

```yaml
deploy_docs:
  stage: deploy
  image: python:3.12-slim
  script:
    - pip install -r requirements.txt
    - python src/deploy.py --directory docs/
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### JSON

```json
{
  "version": 1,
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [{ "type": "text", "text": "Hello ADF" }]
    }
  ]
}
```

### No language (plain text)

```plaintext
This is a plain text code block with no syntax highlighting.
It renders in monospace but without any colour.
```

---

## Blockquotes

A plain blockquote without a type tag:

> This is a blockquote. Use it for quotations, external references, or asides that do
> not require semantic colour coding. It maps to an ADF blockquote node.

A multi-line blockquote:

> First line of the blockquote.
> Second line, still part of the same blockquote.
>
> A second paragraph within the same blockquote.

---

## Panels

All five panel types, each with inline formatting inside.

<!-- markdownlint-disable MD028 -->
> [!info]
> **Info panel.** This is blue. Use it for supplementary information, tips, and background
> context that helps but isn't critical. You can include `inline code` and [links](https://example.com).

> [!note]
> **Note panel.** This is purple. Use it for important details that readers should not skip.
> Notes are higher priority than info but lower than warnings.

> [!warning]
> **Warning panel.** This is yellow. Use it for cautions, potential pitfalls, and things that
> can go wrong. **Always explain what the risk is and how to avoid it.**

> [!success]
> **Success panel.** This is green. Use it for confirmations, prerequisites that have been
> met, or positive outcomes. Great for "you're all set" moments. :white_check_mark:

> [!error]
> **Error panel.** This is red. Use it for errors, breaking changes, critical issues, and
> things that will cause data loss or system failure. Do not use for minor warnings.

A multi-paragraph panel:

> [!warning]
> **Destructive operation.** The following command permanently deletes all data in the
> target environment. There is no undo.
>
> Ensure you have a verified backup before proceeding. Run `verify-backup.sh` first.

---

## Expand blocks

A simple expand:

> [!expand Show the full changelog]
> **v2.1.0** — Added ADF support, panel types, expand blocks.
>
> **v2.0.0** — Rewrote converter from storage format to ADF.
>
> **v1.5.0** — Added table support and alignment.
>
> **v1.0.0** — Initial release with headings and paragraphs.

An expand with a code block inside:

> [!expand View full deploy script output]
>
> ```plaintext
> [INFO]  Resolving space key: DOCS → spaceId: 123456
> [INFO]  Page "My Page" not found — creating new page
> [INFO]  Page created: id=789012
> [INFO]  Labels applied: reference, sample
> [SUCCESS] Deploy complete in 1.23s
> ```

An expand with a list inside:

> [!expand Advanced configuration options — click to expand]
> All settings below override the defaults. Set them in your `.env` file or CI environment.
>
> - `CCFM_MAX_RETRIES` — number of API retry attempts (default: 3)
> - `CCFM_TIMEOUT` — HTTP timeout in seconds (default: 30)
> - `CCFM_BACKOFF` — exponential backoff multiplier (default: 1.5)
> - `CCFM_DRY_RUN` — set to `true` to validate without deploying (default: false)

---

## Tables

### Basic table

| Feature | ADF Node | CCFM Syntax |
| -------- -| --------- -| ------------ -|
| Heading | `heading` | `# H1` through `###### H6` |
| Paragraph | `paragraph` | Plain text block |
| Bold | `strong` mark | `**text**` |
| Italic | `em` mark | `*text*` |
| Code | `codeBlock` | Fenced blocks with language tag |
| Panel | `panel` | `> [!info]` |
| Expand | `expand` | `> [!expand Title]` |

### Table with column alignment

| Left aligned | Centred | Right aligned |
|:------------ -|:-------:| --------------:|
| First row | data | 100 |
| Second row | data | 200 |
| Third row | data | 1,000 |
| Total | — | 1,300 |

### Table with inline formatting in cells

| Status | Component | Last updated | Notes |
| ------- -| ---------- -| ------------- -| ------ -|
| ::Stable::green:: | `converter_adf.py` | @date:2026-02-17 | Full CCFM support |
| ::In Review::blue:: | `deploy.py` | @date:2026-02-15 | Pending ADF migration |
| ::Deprecated::yellow:: | `converter.py` | @date:2026-01-01 | Use `converter_adf.py` |
| ::Blocked::red:: | `validator.py` | @date:2026-02-10 | Awaiting schema pin |

---

## Emoji

Emoji using `:shortname:` syntax:

Build passing :white_check_mark: Deploy failed :x: Review needed :eyes:

Shipped to production :rocket: Great work :tada: Idea :bulb:

Take note :pencil: Work in progress :hammer: Alert :rotating_light:

A paragraph mixing text and emoji: The deploy pipeline :rocket: completed successfully
:white_check_mark: after three retries :rotating_light:. Check the logs :pencil: for details.

---

## Status badges

Inline status labels with different colours:

Current API status: ::Stable::green::

Auth service: ::Degraded::red::

New feature flag: ::In Preview::blue::

Scheduled maintenance: ::Planned::yellow::

Documentation: ::Draft::neutral::

Enterprise tier: ::Enterprise Only::purple::

A sentence mixing status badges with regular text: The payment service is currently
::Stable::green:: and the new checkout flow is ::In Preview::blue::. The legacy API
is ::Deprecated::yellow:: and will be removed on @date:2026-04-01.

---

## Date tokens

Inline date nodes rendered by Confluence in the user's locale:

This specification was drafted on @date:2026-02-17.

The legacy storage format will be fully deprecated on @date:2026-04-01.

The ADF migration was completed on @date:2026-01-21.

A sentence with a date inline: Support for the v1 API ends @date:2026-06-30 at which
point all clients must have migrated to v2.

---

## Everything together

The following paragraph uses every inline element simultaneously to ensure they can
coexist without interfering with each other.
<!-- markdownlint-disable MD059 -->
This sentence has **bold**, *italic*, ***bold italic***, ~~strikethrough~~, ++underline++,
`code`, a [link](https://example.com), a [page link](<CCFM Example - My Team>), an emoji :rocket:,
a status ::Live::green::, a date @date:2026-02-17, superscript x^2^, and subscript H~2~O.
Everything should render independently without breaking adjacent elements.

---

*End of CCFM element reference. If every section above renders correctly in Confluence,
the converter is producing valid ADF for all supported elements.*
