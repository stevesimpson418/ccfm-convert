# Markdownlint Configuration

CCFM ships with a recommended `.markdownlint.jsonc` configuration that works well with
CCFM's syntax extensions. Place this file in your documentation repository root.

## Recommended Configuration

```json
{
  // Default: enable all rules
  "default": true,
  // MD003: Heading style - enforce ATX style (# Heading)
  "MD003": {
    "style": "atx"
  },
  // MD007: Unordered list indentation - 2 spaces
  "MD007": {
    "indent": 2
  },
  // MD013: Line length - disabled (no hard limit on prose)
  "MD013": false,
  // MD024: Allow duplicate headings if they're not siblings
  "MD024": {
    "siblings_only": true
  },
  // MD025: Only one H1 per document — set front_matter_title to "" so the
  // frontmatter `title` field is not counted as the H1. Files can have both
  // a frontmatter title (for Confluence page title) and an H1 in the body.
  "MD025": { "front_matter_title": "" },
  // MD033: Allow inline HTML - needed for Confluence-specific notes
  "MD033": false,
  // MD041: First line doesn't need to be H1 (files have frontmatter)
  "MD041": false,
  // MD046: Code block style - fenced (```) not indented
  "MD046": {
    "style": "fenced"
  }
}
```

## Rule Explanations

| Rule | Setting | Why |
| --- | --- | --- |
| **MD003** | ATX style (`#`) | CCFM only supports ATX-style headings for ADF conversion |
| **MD007** | 2-space indent | Matches CCFM's nested list parsing expectations |
| **MD013** | Disabled | Prose lines in documentation shouldn't have hard length limits |
| **MD024** | Siblings only | Different sections can reuse headings like "Overview" or "Examples" |
| **MD025** | `front_matter_title: ""` | CCFM files have a frontmatter `title` *and* an H1 in the body — don't count the frontmatter title as the first H1 |
| **MD033** | Disabled | Some Confluence-specific markup may use inline HTML |
| **MD041** | Disabled | CCFM files start with YAML frontmatter, not an H1 |
| **MD046** | Fenced | CCFM requires fenced code blocks (triple backticks) for language tagging |
