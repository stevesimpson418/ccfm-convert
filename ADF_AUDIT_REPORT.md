<!-- markdownlint-disable MD060 -->
# ADF Spec Compliance Audit Report

**Date**: 2026-03-23
**Schema source**: `@atlaskit/adf-schema@latest` (stage-0, superset of full.json)
**Codebase**: ccfm-convert @ `e9a89a3` (main)

---

## Executive Summary (updated post-implementation)

| Category | Count | Details |
|----------|-------|---------|
| Supported | 42 | 25 block/media + 8 inline + 9 marks (includes new features) |
| Documented as out of scope | 12 | mention, textColor, backgroundColor, mediaGroup, mediaInline, custom panel, decisionList/Item, blockTaskItem, indentation, fontSize, breakout, border |
| Not yet implemented (feature request filed) | 2 | layoutSection/Column (#38), bodiedExtension/multiBodiedExtension (#39) |
| Not applicable (Confluence internals) | 6 | syncBlock, bodiedSyncBlock, annotation, dataConsumer, fragment, placeholder |
| **Total** | **62** | |

---

## 1. Supported Resources — Spec Compliance

### 1a. Fully Compliant (28)

These are implemented correctly per the ADF JSON schema.

#### Block Nodes

| ADF Node | Our Function | File | Tested | Documented | Notes |
|----------|-------------|------|--------|------------|-------|
| `doc` | `doc()` | nodes.py:61 | Yes | Yes | Correct: `version: 1`, content array |
| `paragraph` | `paragraph()` | nodes.py:71 | Yes | Yes | Correct minimal structure |
| `paragraph` (aligned) | `paragraph_with_alignment()` | nodes.py:76 | Yes | Yes | Correct: alignment mark with `center`/`end` only |
| `heading` | `heading()` | nodes.py:66 | Yes | Yes | Correct: level 1-6 |
| `bulletList` | `bullet_list()` | nodes.py:138 | Yes | Yes | Correct |
| `orderedList` | `ordered_list()` | nodes.py:143 | Yes | Yes | Correct: includes `order` attr |
| `listItem` | `list_item()` | nodes.py:172 | Yes | Yes | Correct |
| `blockquote` | `blockquote()` | nodes.py:115 | Yes | Yes | Correct |
| `codeBlock` | `code_block()` | nodes.py:105 | Yes | Yes | Correct: optional language, text-only content |
| `rule` | `rule()` | nodes.py:100 | Yes | Yes | Correct void node |
| `panel` | `panel()` | nodes.py:120 | Yes | Yes | Correct for 5 types (see 1b for missing types) |
| `expand` | `expand()` | nodes.py:128 | Yes | Yes | Correct: title + content |
| `table` | `table_node()` | nodes.py:182 | Yes | Yes | Correct (see 1b for optional attrs) |
| `tableRow` | `table_row()` | nodes.py:191 | Yes | Yes | Correct |
| `taskList` | `task_list()` | nodes.py:148 | Yes | Yes | Correct: required `localId` (UUID) |
| `taskItem` | `task_item()` | nodes.py:157 | Yes | Yes | Correct: `localId`, `state` (TODO/DONE), inline content |
| `mediaSingle` | `media_single()` | nodes.py:245 | Yes | Yes | Correct: layout + pixel width variant |

#### Inline Nodes

| ADF Node | Our Function | File | Tested | Documented | Notes |
|----------|-------------|------|--------|------------|-------|
| `text` | `text_node()` | nodes.py:221 | Yes | Yes | Correct: text + optional marks |
| `hardBreak` | `hard_break()` | nodes.py:229 | Yes | Yes | Correct void node |
| `inlineCard` | `inline_card()` | nodes.py:234 | Yes | Yes | Correct: URL variant |
| `emoji` | `emoji_node()` | nodes.py:311 | Yes | Yes | Correct: `shortName` required, `id` optional |
| `date` | `date_node()` | nodes.py:340 | Yes | Yes | Correct: millisecond timestamp string |
| `media` | (inside mediaSingle) | nodes.py:245-308 | Yes | Yes | Correct: external + file variants |

#### Marks

| ADF Mark | Our Syntax | Tested | Documented | Notes |
|----------|-----------|--------|------------|-------|
| `strong` | `**text**` | Yes | Yes | Correct: no attrs |
| `em` | `*text*` | Yes | Yes | Correct: no attrs |
| `code` | `` `text` `` | Yes | Yes | Correct: no attrs |
| `strike` | `~~text~~` | Yes | Yes | Correct: no attrs |
| `underline` | `++text++` | Yes | Yes | Correct: no attrs |
| `subsup` | `^text^` / `~text~` | Yes | Yes | Correct: `attrs.type: "sup"/"sub"` |
| `link` | `[text](url)` | Yes | Yes | Correct: `attrs.href` |
| `alignment` | (paragraph mark) | Yes | Yes | Correct: `center`/`end` only |

---

### 1b. Supported with Spec Deviations (3)

These work in practice but deviate from the strict JSON schema.

#### `status` — Color Casing Mismatch

| Aspect | Our Implementation | ADF Schema |
|--------|-------------------|------------|
| `attrs.color` | `"NEUTRAL"`, `"BLUE"`, `"RED"`, etc. (uppercase) | `"neutral"`, `"blue"`, `"red"`, etc. (lowercase enum) |

**Location**: `nodes.py:333` — `color.upper()`
**Impact**: Confluence accepts uppercase in practice, but the JSON schema enum values are lowercase. Strictly speaking, this would fail schema validation.
**Recommendation**: Use lowercase to match the schema. Confluence handles both.

#### `panel` — Missing `tip` and `custom` Types

| Aspect | Our Implementation | ADF Schema |
|--------|-------------------|------------|
| `panelType` values | `info`, `note`, `warning`, `success`, `error` | `info`, `note`, **`tip`**, `warning`, `error`, `success`, **`custom`** |

**Location**: `nodes.py:120`, `blocks.py` panel detection
**Impact**: `tip` is a valid panel type we don't support. `custom` requires additional attrs (`panelIcon`, `panelIconId`, `panelIconText`, `panelColor`).
**Recommendation**: Add `tip` support (trivial — just allow the string). `custom` is lower priority as it needs icon/color attrs.

#### `tableHeader` / `tableCell` — Empty `attrs` Object

| Aspect | Our Implementation | ADF Schema |
|--------|-------------------|------------|
| `attrs` | Always included as `{}` | Optional; when present, only allows `colspan`, `rowspan`, `colwidth`, `background`, `localId` |

**Location**: `nodes.py:203`, `nodes.py:213`
**Impact**: Including an empty `attrs: {}` object is technically valid (no unknown keys), but unnecessary. Schema treats `attrs` as optional on these nodes.
**Recommendation**: Low priority. Works correctly but adds unnecessary bytes to ADF output.

---

## 2. Documented as Out of Scope (6)

These ADF features are explicitly documented in CCFM.md (lines 710-720) as intentionally excluded.

| ADF Feature | Reason Documented | Schema Required Attrs | Assessment |
|-------------|-------------------|----------------------|------------|
| `mention` | Requires raw Atlassian account IDs | `attrs.id` (account ID string) | Reasonable exclusion — no markdown-friendly way to express account IDs |
| `textColor` | Accessibility liability; no markdown syntax | `attrs.color` (#6hex) | Reasonable — accessibility concern valid |
| `backgroundColor` | No markdown equivalent; accessibility | `attrs.color` (#6hex) | Reasonable — same rationale as textColor |
| `media` (direct) | Created automatically inside mediaSingle | type/id/collection or type/url | Correct — media is always a child node, not authored directly |
| `mediaGroup` | Editor-only layout feature | content: array of media nodes | Reasonable — primarily used by Confluence editor |
| `mediaInline` | Editor-only inline image variant | `attrs.id`, `attrs.collection` | Reasonable — editor-managed inline images |

---

## 3. Missing from Documentation — Should Document as Unsupported (18)

These ADF features exist in the schema but are **not implemented AND not documented** as out of scope. They should be added to the "Deliberately out of scope" table in CCFM.md or flagged as future work.

### Block Nodes (12)

| ADF Node | What It Does | Potential CCFM Syntax | Priority |
|----------|-------------|----------------------|----------|
| `nestedExpand` | Expand inside another expand or table cell | Could auto-generate when expand is inside a table | Medium — would improve table UX |
| `blockCard` | Full-width smart link card (Jira issues, Confluence pages) | `!![Text](url)` or similar | Medium — useful for embedding Jira issues |
| `embedCard` | Embedded iframe/preview (videos, external content) | Could use `@embed(url)` syntax | Medium — YouTube/Loom embeds are common |
| `layoutSection` | Multi-column page layout (2-5 columns) | Fenced syntax like `:::columns` | High — frequently requested Confluence feature |
| `layoutColumn` | Column within a layout section | Child of layoutSection | High — paired with layoutSection |
| `extension` | Confluence macro (no body) — e.g., TOC, JIRA filter | `@macro(key)` or directive syntax | High — TOC macro alone is very popular |
| `bodiedExtension` | Confluence macro with body content | Fenced directive with content | Medium — code-block macros, excerpt, etc. |
| `multiBodiedExtension` | Multi-tab macro content | Complex nested syntax | Low — rarely authored manually |
| `extensionFrame` | Frame within multiBodiedExtension | Child of multiBodiedExtension | Low — paired with multiBodiedExtension |
| `decisionList` | Decision tracking list (like taskList but for decisions) | `- [?] decision text` | Low — niche Confluence feature |
| `decisionItem` | Item within a decisionList | Child of decisionList | Low — paired with decisionList |
| `blockTaskItem` | Block-level task item (paragraphs, not inline) | Extended task syntax | Low — taskItem covers most use cases |

### Sync Blocks (2)

| ADF Node | What It Does | Potential CCFM Syntax | Priority |
|----------|-------------|----------------------|----------|
| `syncBlock` | Reference to shared/synced content block | N/A — requires Confluence runtime IDs | Not applicable — Confluence-managed |
| `bodiedSyncBlock` | Inline synced content block with body | N/A — requires Confluence runtime IDs | Not applicable — Confluence-managed |

### Marks (6)

| ADF Mark | What It Does | Potential CCFM Syntax | Priority |
|----------|-------------|----------------------|----------|
| `annotation` | Inline comment anchor | N/A — Confluence editor feature | Not applicable — editor-managed |
| `indentation` | Paragraph/heading indent level (1-6) | Could use `>` depth or `{indent=N}` | Low — rarely needed in docs |
| `fontSize` | Small text (only `"small"` allowed) | `{size=small}` or `<small>` | Low — schema only allows "small" |
| `breakout` | Wide/full-width block display | Already handled via mediaSingle layout | Low — could add to codeBlock/expand |
| `border` | Border on media nodes (size 1-3, color) | `{border=1}` on images | Low — cosmetic |
| `dataConsumer` | Links extensions to data sources | N/A — internal Confluence wiring | Not applicable — system-managed |
| `fragment` | Cross-document fragment reference | N/A — internal Confluence wiring | Not applicable — system-managed |

### Inline Nodes (2)

| ADF Node | What It Does | Potential CCFM Syntax | Priority |
|----------|-------------|----------------------|----------|
| `placeholder` | Editor placeholder text | N/A — editor-only, not in published content | Not applicable — editor UI only |
| `inlineExtension` | Inline macro (e.g., inline Jira issue) | `@jira(KEY-123)` or similar | Medium — inline Jira refs are useful |

### Media (1)

| ADF Node | What It Does | Potential CCFM Syntax | Priority |
|----------|-------------|----------------------|----------|
| `caption` | Image caption (child of mediaSingle) | `![alt](url "caption text")` | Medium — would improve image docs |

---

## 4. Complete ADF Schema Coverage Matrix

Every node, mark, and inline type from the ADF schema, with current status.

### All Block Nodes (31 total)

| # | ADF Node | Status | Spec Compliant | Tested | In CCFM.md |
|---|----------|--------|----------------|--------|-------------|
| 1 | `doc` | Supported | Yes | Yes | Yes |
| 2 | `paragraph` | Supported | Yes | Yes | Yes |
| 3 | `heading` | Supported | Yes | Yes | Yes |
| 4 | `bulletList` | Supported | Yes | Yes | Yes |
| 5 | `orderedList` | Supported | Yes | Yes | Yes |
| 6 | `listItem` | Supported | Yes | Yes | Yes |
| 7 | `blockquote` | Supported | Yes | Yes | Yes |
| 8 | `codeBlock` | Supported | Yes | Yes | Yes |
| 9 | `rule` | Supported | Yes | Yes | Yes |
| 10 | `panel` | Supported | Partial (missing tip/custom) | Yes | Yes |
| 11 | `table` | Supported | Yes | Yes | Yes |
| 12 | `tableRow` | Supported | Yes | Yes | Yes |
| 13 | `tableCell` | Supported | Yes (empty attrs minor) | Yes | Yes |
| 14 | `tableHeader` | Supported | Yes (empty attrs minor) | Yes | Yes |
| 15 | `taskList` | Supported | Yes | Yes | Yes |
| 16 | `taskItem` | Supported | Yes | Yes | Yes |
| 17 | `expand` | Supported | Yes | Yes | Yes |
| 18 | `mediaSingle` | Supported | Yes | Yes | Yes |
| 19 | `media` | Supported | Yes | Yes | Documented as auto-created |
| 20 | `blockTaskItem` | Not implemented | — | — | No |
| 21 | `decisionList` | Not implemented | — | — | No |
| 22 | `decisionItem` | Not implemented | — | — | No |
| 23 | `nestedExpand` | Not implemented | — | — | No |
| 24 | `blockCard` | Not implemented | — | — | No |
| 25 | `embedCard` | Not implemented | — | — | No |
| 26 | `layoutSection` | Not implemented | — | — | No |
| 27 | `layoutColumn` | Not implemented | — | — | No |
| 28 | `extension` | Not implemented | — | — | No |
| 29 | `bodiedExtension` | Not implemented | — | — | No |
| 30 | `multiBodiedExtension` | Not implemented | — | — | No |
| 31 | `extensionFrame` | Not implemented | — | — | No |
| 32 | `syncBlock` | Not applicable | — | — | No |
| 33 | `bodiedSyncBlock` | Not applicable | — | — | No |

### All Inline Nodes (10 total)

| # | ADF Node | Status | Spec Compliant | Tested | In CCFM.md |
|---|----------|--------|----------------|--------|-------------|
| 1 | `text` | Supported | Yes | Yes | Yes |
| 2 | `hardBreak` | Supported | Yes | Yes | Yes |
| 3 | `emoji` | Supported | Yes | Yes | Yes |
| 4 | `date` | Supported | Yes | Yes | Yes |
| 5 | `status` | Supported | Deviation (color casing) | Yes | Yes |
| 6 | `inlineCard` | Supported | Yes | Yes | Yes |
| 7 | `mention` | Out of scope | — | — | Yes (documented) |
| 8 | `placeholder` | Not applicable | — | — | No (editor-only) |
| 9 | `inlineExtension` | Not implemented | — | — | No |
| 10 | `mediaInline` | Out of scope | — | — | Yes (documented) |

### All Media Nodes (5 total)

| # | ADF Node | Status | Spec Compliant | Tested | In CCFM.md |
|---|----------|--------|----------------|--------|-------------|
| 1 | `media` | Supported | Yes | Yes | Yes (as child of mediaSingle) |
| 2 | `mediaSingle` | Supported | Yes | Yes | Yes |
| 3 | `mediaGroup` | Out of scope | — | — | Yes (documented) |
| 4 | `mediaInline` | Out of scope | — | — | Yes (documented) |
| 5 | `caption` | Not implemented | — | — | No |

### All Marks (17 total)

| # | ADF Mark | Status | Spec Compliant | Tested | In CCFM.md |
|---|----------|--------|----------------|--------|-------------|
| 1 | `strong` | Supported | Yes | Yes | Yes |
| 2 | `em` | Supported | Yes | Yes | Yes |
| 3 | `strike` | Supported | Yes | Yes | Yes |
| 4 | `underline` | Supported | Yes | Yes | Yes |
| 5 | `code` | Supported | Yes | Yes | Yes |
| 6 | `link` | Supported | Yes | Yes | Yes |
| 7 | `subsup` | Supported | Yes | Yes | Yes |
| 8 | `alignment` | Supported | Yes | Yes | Yes |
| 9 | `textColor` | Out of scope | — | — | Yes (documented) |
| 10 | `backgroundColor` | Out of scope | — | — | Yes (documented) |
| 11 | `annotation` | Not applicable | — | — | No (editor-managed) |
| 12 | `indentation` | Not implemented | — | — | No |
| 13 | `fontSize` | Not implemented | — | — | No |
| 14 | `breakout` | Not implemented | — | — | No |
| 15 | `border` | Not implemented | — | — | No |
| 16 | `dataConsumer` | Not applicable | — | — | No (system-managed) |
| 17 | `fragment` | Not applicable | — | — | No (system-managed) |

---

## 5. Additional Schema Constraints Not Currently Enforced

These are schema rules that our code doesn't explicitly enforce but may matter for edge cases:

| Constraint | Schema Rule | Our Behaviour | Risk |
|-----------|------------|---------------|------|
| `text.text` minLength | Must be >= 1 character | No validation | Low — empty text nodes unlikely in practice |
| `codeBlock` text marks | Text children must have `maxItems: 0` marks | We don't add marks to code text | None — correct by construction |
| `blockquote` content | Cannot contain headings, panels, tables, or expands | We allow panels inside blockquotes (panel syntax) | Medium — we convert `> [!info]` to panel, not blockquote+panel |
| `expand` nesting | Cannot nest `expand` inside `expand` (use `nestedExpand`) | No nesting support | None — we don't generate nested expands |
| `table.localId` | If present, `minLength: 1` | We don't set localId on tables | None |
| `tableCell` colspan/rowspan | Supported in schema but not in our converter | Skipped tests flag this | Low — GFM tables don't support colspan |

---

## 6. Recommended Actions

### Quick Wins (Spec Compliance)

1. **Fix status color casing** — Change `color.upper()` to `color.lower()` in `nodes.py:333`. This aligns with the schema enum values. Confluence accepts both but lowercase is spec-correct.

2. **Add `tip` panel type** — Allow `> [!tip]` in blockquote-to-panel detection. Trivial change to `blocks.py`.

3. **Document missing ADF features** — Add the 18 undocumented features to the "Deliberately out of scope" table in CCFM.md, grouped by reason:
   - Not applicable (Confluence-managed): `syncBlock`, `bodiedSyncBlock`, `annotation`, `dataConsumer`, `fragment`, `placeholder`
   - Future consideration: `layoutSection/Column`, `extension/bodiedExtension`, `blockCard`, `embedCard`, `caption`, `nestedExpand`, `inlineExtension`
   - Low priority: `decisionList/Item`, `blockTaskItem`, `indentation`, `fontSize`, `breakout`, `border`, `multiBodiedExtension/extensionFrame`

### Future Feature Candidates (by user value)

| Priority | Feature | Effort | User Value |
|----------|---------|--------|------------|
| High | `layoutSection` + `layoutColumn` | Medium | Multi-column layouts very popular |
| High | `extension` (macros like TOC, Jira filter) | Medium | TOC macro alone is high demand |
| Medium | `blockCard` / `embedCard` | Low-Medium | Smart link embeds (Jira, YouTube) |
| Medium | `caption` on mediaSingle | Low | Image captions improve docs |
| Medium | `inlineExtension` | Low | Inline Jira issue references |
| Low | `bodiedExtension` | Medium | Excerpt, code-block macros |
| Low | `nestedExpand` | Low | Expand inside tables |
| Low | `tip` panel type | Trivial | Already close to done |
