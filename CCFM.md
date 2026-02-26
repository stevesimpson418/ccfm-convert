# Confluence Cloud Flavoured Markdown (CCFM)

Confluence Cloud Flavoured Markdown (CCFM) is a superset of standard Markdown that converts
to native Atlassian Document Format (ADF) — the format used by Confluence Cloud's editor.
Because CCFM compiles directly to ADF, pages open in the cloud editor without any legacy
conversion, smart links work correctly, and Rovo can index all content.

CCFM is designed to feel familiar. If you write Markdown for GitHub, GitLab, or Obsidian,
you already know most of it.

---

## Differences from standard Markdown

CCFM is based on [CommonMark](https://spec.commonmark.org/) with extensions from
[GitHub Flavored Markdown (GFM)](https://github.github.com/gfm/). Everything that works
in standard Markdown works in CCFM. The following features are CCFM-specific:

**Not found in standard Markdown:**

- [Front matter](#front-matter) — page metadata (title, labels, parent, space)
- [Panels](#panels) — coloured callout blocks (info, note, warning, success, error)
- [Expand blocks](#expand-blocks) — collapsible sections
- [Status badges](#status-badges) — inline coloured status labels
- [Confluence page links](#confluence-page-links) — links to other Confluence pages by title
- [Emoji](#emoji) — `:shortname:` emoji using Atlassian's emoji set
- [Date tokens](#date-tokens) — inline rendered date nodes

**Extended from standard Markdown:**

| Standard Markdown | Extended in CCFM |
| --- | --- |
| Code blocks | Language-tagged syntax highlighting |
| Blockquotes | Panels with semantic type (info, warning, etc.) |
| Links | Internal Confluence page links via `[Text](<Title>)` |
| Horizontal rule | Maps to ADF `rule` node |

---

## Front matter

Every CCFM file should begin with a YAML front matter block. This controls where and how
the page is published in Confluence.

```yaml
---
page_meta:
  title: My Page Title
  parent: Architecture Overview   # Optional — overrides directory-based hierarchy
  author: Jane Smith              # Optional — added as a label
  labels:
    - backend
    - api
    - v2
  attachments:
    - path: diagram.png
      alt: "Architecture diagram"
    - path: screenshot.png
      alt: "Dashboard screenshot"

deploy_config:
  ci_banner: true                 # Show managed-by-CI banner (default: true)
  page_status: "current"          # "current" or "draft" (default: current)
  deploy_page: true               # Set to false to skip deployment
---
```

### Front matter fields

#### `page_meta`

| Field | Required | Description |
| --- | --- | --- |
| `title` | No | The page title as it appears in Confluence. Defaults to filename. |
| `parent` | No | Title of the parent page. Overrides directory-based hierarchy if set. Page is created at space root if omitted and file is in the deploy root. |
| `author` | No | Author name — added as an `author-*` label |
| `labels` | No | List of Confluence labels to apply to the page |
| `attachments` | No | List of files to attach. Each item has `path` (relative to markdown file) and optional `alt` text |

#### `deploy_config`

| Field | Required | Description |
| --- | --- | --- |
| `ci_banner` | No | Show the managed-by-CI banner (default: `true`) |
| `ci_banner_text` | No | Custom banner text (optional) |
| `include_page_metadata` | No | Show page metadata in an expand block (default: `false`) |
| `page_status` | No | `"current"` or `"draft"` (default: `"current"`) |
| `deploy_page` | No | Set to `false` to skip deployment entirely (default: `true`) |

The front matter block is never rendered as content. It is consumed by the deploy tool only.

---

## Headings

Create headings using `#`. Confluence supports H1 through H6.

```markdown
# H1 — Page title (use once per page)
## H2 — Major section
### H3 — Subsection
#### H4
##### H5
###### H6
```

> **Note:** Use a single H1 per page. It does not need to match the front matter `title` —
> but it usually should. Skipping heading levels (e.g. H1 → H3) is valid but not recommended
> for accessibility or navigation.

---

## Paragraphs and line breaks

Separate paragraphs with a blank line.

```markdown
This is the first paragraph.

This is the second paragraph.
```

### Hard line breaks

Force a line break within a paragraph using a trailing backslash `\` or two trailing spaces.

```markdown
First line of a paragraph.\
Second line, same paragraph.

First line with two spaces.
Second line, same paragraph.
```

Both produce an ADF `hardBreak` node — a newline without starting a new paragraph.

---

## Emphasis

```markdown
*italic* or _italic_

**bold** or __bold__

***bold italic***

~~strikethrough~~
```

You can combine marks freely:

```markdown
You can have **bold and _italic_ together**.

This is ~~struck through with **bold** inside~~.
```

---

## Underline

Use `++text++` for underline.

```markdown
This word is ++underlined++.
```

> **Use sparingly.** Underline is commonly associated with hyperlinks. Avoid underlining
> text that is not a link to prevent confusion.

---

## Superscript and subscript

Use `^` for superscript and `~` for subscript (single word, no spaces).

```markdown
E = mc^2^

H~2~O

2^10^ = 1024
```

> **Note:** `~` for subscript and `~~` for strikethrough are distinguished by count.
> Single `~word~` (no spaces) is subscript. Double `~~word~~` is strikethrough.

---

## Inline code

Wrap text in single backticks for inline code.

```markdown
Use the `deploy` command to publish pages.

Set the `CONFLUENCE_TOKEN` environment variable before running.
```

---

## Links

### External links

Standard Markdown link syntax.

```markdown
[Atlassian Developer Docs](https://developer.atlassian.com/)
```

### Confluence page links

To link to another page within Confluence, use angle brackets around the page title instead
of a URL. CCFM converts this to an ADF `inlineCard` node — Confluence resolves the title
to the live page and renders it as a smart link.

```markdown
[Getting Started](<Getting Started>)

[See the API Reference](<API Reference Guide>)
```

> **Note:** The page title inside `<>` must exactly match the Confluence page title, including
> capitalisation. CCFM does not validate this at compile time — a wrong title will result in
> an unresolved card in Confluence.

---

## Images

### External images

Standard Markdown image syntax. The image must be accessible via URL.

```markdown
![Alt text](https://example.com/image.png)

![Architecture diagram](https://example.com/arch.png "Optional title")
```

Renders as an ADF `mediaSingle` node. The default display width is 760px, matching the standard
Confluence page width.

### Image width

Control the display width by appending `{width=VALUE}` to the image line:

```markdown
![Diagram](https://example.com/diagram.png){width=max}

![Logo](https://example.com/logo.png){width=wide}

![Thumbnail](https://example.com/thumb.png){width=200}
```

| Value | Effect |
| --- | --- |
| _(none)_ | 760px centred — default, matches the standard Confluence page width |
| `narrow` | 760px centred — same as default, explicit form |
| `wide` | Extends into the page margin area |
| `max` | Edge-to-edge, full page width |
| _integer_ | Custom pixel width, centred (e.g. `{width=500}`) |

### Local images (attachments)

Embed a locally stored image using two complementary declarations.

**1. Reference the file by filename in the markdown body:**

```markdown
![Architecture diagram](diagram.png)

![Architecture diagram](diagram.png){width=max}
```

**2. Declare the file in the frontmatter `attachments` list:**

```yaml
page_meta:
  attachments:
    - path: diagram.png           # Relative to the markdown file
      alt: "Architecture diagram" # Attachment label in Confluence
      width: max                  # Optional — overrides the {width=} in the markdown body
```

The deploy tool uploads the file, fetches its Media Services ID from Confluence, and rewrites
the ADF media node with the correct attachment reference. The `alt` field sets the attachment
label in Confluence; the alt text displayed on the page comes from the markdown `![alt text]`
syntax.

> **Note:** Both the markdown reference _and_ the frontmatter `attachments` entry are required.
> If `width` is set in both places, the frontmatter value takes precedence.

---

## Horizontal rule

Three or more hyphens on their own line.

```markdown
---
```

Renders as an ADF `rule` node — a full-width horizontal divider.

---

## Lists

### Unordered lists

Use `-`, `*`, or `+` followed by a space.

```markdown
- First item
- Second item
- Third item
```

### Ordered lists

Use a number followed by `.` and a space. The actual numbers don't matter — Confluence
numbers them sequentially.

```markdown
1. First step
2. Second step
3. Third step
```

### Nested lists

Indent by two or four spaces to create nested lists. You can mix ordered and unordered.

```markdown
- Item one
  - Nested item
  - Another nested item
    - Deeply nested
- Item two

1. First
   1. Sub-first
   2. Sub-second
2. Second
```

---

## Task lists

Task lists (also called checklists or action items) use GFM checkbox syntax. They render
as interactive checkboxes in Confluence that can be checked/unchecked.

```markdown
- [ ] Unchecked task
- [x] Checked task
- [ ] Another unchecked task
```

### Task lists with inline formatting

Task items can contain inline formatting:

```markdown
- [ ] Review **pull request #123**
- [x] Deploy to `staging` environment
- [ ] Update [documentation](<User Guide>)
- [ ] Notify team :rocket:
```

> **Note:** In Confluence, task items are rendered with checkboxes that persist state.
> Checking a box in Confluence updates the page — it does not modify the source markdown.
>
> **Limitation:** Task items contain inline content only. Unlike regular lists, task items
> cannot contain nested lists or multiple paragraphs. This is an ADF schema constraint.

---

## Code blocks

Fenced code blocks use triple backticks. Specify a language for syntax highlighting.

````markdown
```python
def hello(name: str) -> str:
    return f"Hello, {name}"
```
````

````markdown
```bash
git commit -m "initial commit"
```
````

A code block without a language tag should use `plaintext` for better linter compatibility:

````markdown
```plaintext
plain text, no highlighting
```
````

### Supported languages

Any language identifier supported by Confluence's code macro. Common values:

`python`, `javascript`, `typescript`, `java`, `kotlin`, `go`, `rust`, `ruby`, `php`,
`c`, `cpp`, `csharp`, `bash`, `shell`, `sql`, `yaml`, `json`, `xml`, `html`, `css`,
`dockerfile`, `terraform`, `groovy`, `scala`, `swift`, `markdown`, `plaintext`

---

## Blockquotes

Use `>` for a simple blockquote without a type tag. Maps to an ADF `blockquote` node.

```markdown
> This is a blockquote. Use it for quoted text or asides that
> don't need semantic colour coding.
```

For semantic callouts, see [Panels](#panels) below.

---

## Panels

Panels are coloured callout blocks. They use the GitHub/Obsidian callout syntax with
a `[!type]` tag on the first line of a blockquote.

```markdown
> [!info]
> This is an info panel. Use it for supplementary information.

> [!note]
> This is a note panel. Use it for important details worth highlighting.

> [!warning]
> This is a warning panel. Use it for caution or potential pitfalls.

> [!success]
> This is a success panel. Use it for positive outcomes or confirmations.

> [!error]
> This is an error panel. Use it for errors, dangers, or critical issues.
```

### Panel types

| Type | Colour | Use for |
| --- | --- | --- |
| `info` | Blue | Background information, tips, supplementary context |
| `note` | Purple | Things worth noting, important details |
| `warning` | Yellow | Caution, potential gotchas, things that can go wrong |
| `success` | Green | Positive confirmations, prerequisites met, good outcomes |
| `error` | Red | Errors, dangers, breaking changes, critical issues |

### Multi-line panels

A panel can contain multiple lines and inline formatting:

```markdown
> [!warning]
> **Destructive operation.** Running this command will permanently delete all data
> in the target environment.
>
> Ensure you have a backup before proceeding. See [Backup Guide](<Backup Guide>).
```

---

## Expand blocks

An expand block creates a collapsible section. Click the title to show or hide the content.
Use the `[!expand]` tag followed by the title on the same line.

```markdown
> [!expand Click to see the full error log]
> ```
> ERROR 2026-02-17 14:23:11 - Connection refused
> FATAL 2026-02-17 14:23:20 - Max retries exceeded
> ```

> [!expand Advanced configuration options]
> These settings are for advanced users only.
>
> - `max_retries` — number of retry attempts (default: 3)
> - `timeout` — connection timeout in seconds (default: 30)
> - `backoff_factor` — exponential backoff multiplier (default: 1.5)
```

The text after `[!expand` (up to the closing `]`) is the expand title.

---

## Tables

Standard GFM pipe table syntax.

```markdown
| Name       | Type   | Required | Default |
|------------|--------|----------|---------|
| `title`    | string | Yes      | —       |
| `space`    | string | Yes      | —       |
| `parent`   | string | No       | null    |
| `labels`   | list   | No       | []      |
```

### Alignment

Use `:` in the separator row to control column alignment:

```markdown
| Left aligned | Centred | Right aligned |
|:-------------|:-------:|--------------:|
| text         | text    |          text |
```

> **Tables without headers:** ADF requires at least one header row. The first row of every
> CCFM table is always treated as a header and rendered with `tableHeader` cells.

---

## Emoji

Use `:shortname:` syntax. CCFM maps short names to Atlassian's emoji set.

```markdown
Build passing :white_check_mark:

Deploy failed :x:

Review requested :eyes:

Shipped :rocket:
```

Common emoji:

| Syntax | Character |
| --- | --- |
| `:white_check_mark:` | ✅ |
| `:x:` | ❌ |
| `:warning:` | ⚠️ |
| `:rocket:` | 🚀 |
| `:eyes:` | 👀 |
| `:tada:` | 🎉 |
| `:bulb:` | 💡 |
| `:memo:` | 📝 |
| `:hammer:` | 🔨 |
| `:rotating_light:` | 🚨 |

A full list of supported Atlassian emoji short names is available at
<https://confluence.atlassian.com/doc/confluence-emoticons-108565089.html>.

---

## Status badges

Status badges render as inline coloured label nodes in Confluence. Useful for showing
the state of a component, feature, or task directly in documentation.

**Syntax:** `::text::color::`

```markdown
API Status: ::Stable::green::

Feature flag: ::In Preview::blue::

Breaking change: ::Breaking::red::

Maintenance: ::Deprecated::yellow::

Not started: ::Backlog::neutral::
```

### Status colours

| Value | Renders as |
| --- | --- |
| `neutral` | Grey |
| `blue` | Blue |
| `red` | Red |
| `yellow` | Yellow / Amber |
| `green` | Green |
| `purple` | Purple |

Status text can contain spaces. Keep it short — status badges are inline labels, not sentences.

---

## Date tokens

Render an inline date node using ISO 8601 date format prefixed with `@date:`.

```markdown
This decision was made on @date:2026-02-17.

Deprecation target: @date:2026-04-01.
```

Confluence renders date nodes as formatted, localised dates based on the user's locale
setting (e.g. `17 Feb 2026` or `Feb 17, 2026`).

---

## Accessibility

When writing CCFM documentation:

- **Use one H1 per page.** It should match the front matter `title`.
- **Don't skip heading levels.** Go H1 → H2 → H3, not H1 → H3.
- **Write meaningful link text.** `[here]` and `[click here]` are not descriptive.
  Use `[Deployment Guide](<Deployment Guide>)` instead.
- **Write alt text for images.** `![Architecture overview showing three services](url)` is
  better than `![image](url)`.
- **Don't use colour as the only signal.** Status badges have text labels — that's the point.
- **Keep tables accessible.** Every table must have a header row. Avoid empty cells.

---

## Escape characters

Prefix any CCFM or Markdown character with `\` to render it literally.

```markdown
\*not italic\*

\`not code\`

\> not a blockquote

\[not a link\](https://example.com)
```

To render a literal backslash, use `\\`.

---

## Unsupported standard Markdown

The following standard Markdown features produce a best-effort result or are ignored.

| Feature | Behaviour in CCFM |
| --- | --- |
| HTML tags | Stripped. ADF is JSON, not HTML. |
| Footnotes | Rendered as plain text with `[^1]` visible |
| Definition lists | Rendered as plain paragraphs |
| Mermaid / diagrams | Stripped. Use Confluence's built-in diagram macros post-deploy. |
| Math / LaTeX | Stripped. No ADF equivalent. |
| Heading IDs `{#custom-id}` | Stripped. ADF headings don't support custom anchors. |

---

## ADF node reference

Complete mapping of every supported ADF node and mark to its CCFM syntax.

### Block nodes

| ADF Node | CCFM Syntax | Notes |
| --- | --- | --- |
| `doc` | Entire file | Root node, always implicit |
| `heading` | `#` through `######` | H1–H6 |
| `paragraph` | Plain text block | Separated by blank lines |
| `bulletList` | `- item` or `* item` | Unordered list |
| `orderedList` | `1. item` | Ordered list |
| `listItem` | Indented list lines | Child of list nodes |
| `taskList` | `- [ ] item` or `- [x] item` | Checkbox list |
| `taskItem` | Checkbox list item | Child of taskList, has state attr |
| `codeBlock` | ` ```lang ``` ` | Fenced, with optional language |
| `blockquote` | `> text` (no type tag) | Plain quote |
| `rule` | `---` | Horizontal divider |
| `table` | GFM pipe table | First row always header |
| `tableRow` | Table row | Implicit in table syntax |
| `tableHeader` | First row of table | Rendered bold, shaded |
| `tableCell` | Table cell | Alignment via `:` in separator |
| `panel` | `> [!info]` etc. | Five types: info, note, warning, success, error |
| `expand` | `> [!expand Title]` | Collapsible section |
| `mediaSingle` | `![alt](url)` or `![alt](url){width=VALUE}` | Image block; width preset or pixel value |

### Inline nodes

| ADF Node | CCFM Syntax | Notes |
| --- | --- | --- |
| `text` | Plain text | Foundation of all content |
| `hardBreak` | Trailing `\` or two spaces | Newline within paragraph |
| `inlineCard` | `[Text](<Page Title>)` | Confluence smart page link |
| `emoji` | `:shortname:` | Atlassian emoji set |
| `status` | `::text::color::` | Coloured inline label |
| `date` | `@date:YYYY-MM-DD` | Localised date node |

### Marks

| ADF Mark | CCFM Syntax | Notes |
| --- | --- | --- |
| `strong` | `**text**` | Bold |
| `em` | `*text*` or `_text_` | Italic |
| `code` | `` `text` `` | Inline code |
| `strike` | `~~text~~` | Strikethrough |
| `link` | `[text](url)` | External hyperlink |
| `underline` | `++text++` | Use sparingly |
| `subsup` superscript | `^text^` | Superscript |
| `subsup` subscript | `~text~` | Subscript (single word, no spaces) |

### Deliberately out of scope

| ADF Feature | Reason |
| --- | --- |
| `mention` | Requires raw Atlassian account IDs — not author-friendly |
| `textColor` | Accessibility liability; no standard markdown syntax; low practical value |
| `backgroundColor` | No markdown equivalent; conflicts with accessibility |
| `media` | Created automatically inside `mediaSingle` for local attachments; not authored directly |
| `mediaGroup` | Editor-only layout feature |
| `mediaInline` | Editor-only inline image variant |
