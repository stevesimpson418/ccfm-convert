# Changelog

All notable changes to CCFM are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-03-05

### Changed

- `--plan` now exits 0 by default, even when changes are pending (CI-friendly)
- New `--plan-exit-code` flag opts in to Terraform-style exit codes (0 = no
  changes, 2 = changes pending) for CI gating workflows

## [0.1.2] - 2026-03-05

### Fixed

- Docker image now works correctly with GitLab CI and other CI runners that
  inject shell scripts, and tolerates `docker run ... image ccfm --flags`
  (previously doubled the `ccfm` command)

## [0.1.1] - 2026-03-05

### Fixed

- `--changed-only` with zero changes no longer traverses the full directory tree
  or runs orphan archiving — it exits immediately with `No changes to deploy.`
  ([#3](https://github.com/stevesimpson418/ccfm-convert/issues/3))
- `--archive-orphans` combined with `--changed-only` no longer archives pages
  that were simply unchanged on disk; orphan detection now uses the full set of
  current files rather than the changed-files-only subset
  ([#3](https://github.com/stevesimpson418/ccfm-convert/issues/3))
- Broken GHCR badge URL in README replaced with static shields.io badge

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

[0.2.0]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/stevesimpson418/ccfm-convert/releases/tag/v0.1.0
