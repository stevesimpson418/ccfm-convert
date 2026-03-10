# Changelog

All notable changes to CCFM are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-03-10

### Added

- Remote state backend: state stored as a versioned JSON attachment on the CCFM
  management page in Confluence, replacing the local `.ccfm-state.json` file
- Distributed locking: `ccfm lock acquire/status/release` and automatic
  lock acquire/release around all state-writing operations (`deploy`,
  `state rm`, `state push`) to prevent concurrent torn-state scenarios
- `ccfm init`: idempotent bootstrap command that creates the `_ccfm` container
  page and `CCFM State Management` child page in a Confluence space
- `ccfm state pull`: print remote state JSON to stdout (pipe-friendly)
- `ccfm state push <file>`: overwrite remote state from a local JSON file
  (validates schema and `page_id` format before acquiring lock)
- `ccfm state show <path>`: display the state entry for a specific tracked path
- Hierarchy container pages tracked in state so they are not falsely flagged
  as orphans on subsequent deploys
- HTTP retry adapter on all API calls (GET/PUT/DELETE only — POST excluded
  to prevent duplicate page creation on transient 5xx errors)
- Symlink escape guard in `ensure_page_hierarchy` rejects paths that resolve
  outside the docs root
- README Initial Setup section and full CLI reference for all subcommands

### Changed

- `all_pages` and `raw_state` now return deep copies, preventing callers from
  accidentally mutating internal state through the returned dicts
- Orphan archive loop batches the single `state.save()` call after all
  removals instead of saving once per deleted page
- Smoke test teardown resets the state attachment to empty rather than
  deleting management infrastructure, making test runs idempotent

## [0.2.1] - 2026-03-06

_Re-release of 0.2.0 — PyPI rejected the re-uploaded artifacts after a tag
fix; no code changes._

## [0.2.0] - 2026-03-05 [YANKED]

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

[0.3.0]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/stevesimpson418/ccfm-convert/releases/tag/v0.1.0
