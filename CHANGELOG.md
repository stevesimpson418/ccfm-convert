# Changelog

All notable changes to CCFM are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-03-05

### Added

- Markdown to Atlassian Document Format (ADF) conversion engine
- CCFM syntax extensions: status badges, panels, expand blocks, date tokens,
  smart Confluence page links, underline/superscript/subscript, emoji, image width control
- Confluence Cloud REST API deployment (single file and directory tree)
- Automatic Confluence page hierarchy from directory structure
- `.page_content.md` for controlling container page titles and content
- Attachment upload with Confluence Media Services integration
- CI banner injection with source file links (`--git-repo-url`)
- `--dump` mode: write ADF JSON locally without deploying
- State management (`.ccfm-state.json`) with SHA-256 content hashing
- `--plan` mode: Terraform-style diff; exits 2 (changes pending) or 0 (up to date)
- `--changed-only`: skip files with unchanged content
- `--archive-orphans`: delete Confluence pages for removed markdown files
- `ccfm.yaml` project config file with `${ENV_VAR}` interpolation
- 100% unit test coverage; end-to-end smoke tests against real Confluence

[0.1.0]: https://github.com/stevesimpson418/ccfm-convert/releases/tag/v0.1.0
