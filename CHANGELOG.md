# Changelog

All notable changes to CCFM are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-03-13

### Added

- MkDocs Material documentation site deployed to GitHub Pages
- CCFM logo in site navigation and favicon
- GitHub Actions workflow for automatic docs deployment on push to `main`

### Fixed

- GitHub Action argument ordering for v0.4.0 subcommand CLI
  ([#12](https://github.com/stevesimpson418/ccfm-convert/issues/12))

### Changed

- README slimmed to quickstart; full documentation now lives at
  [stevesimpson418.github.io/ccfm-convert](https://stevesimpson418.github.io/ccfm-convert/)
- First stable release

## [0.5.0] - 2026-03-11

### Added

- `deploy_page: false` in frontmatter now generates a **destroy** action for
  previously deployed pages, removing them from Confluence on next `apply`
  ([#8](https://github.com/stevesimpson418/ccfm-convert/issues/8))
- Container pages are also destroyed when all their children have
  `deploy_page: false`
- Manual test steps (5.7–5.12) for `deploy_page: false` destroy workflow

## [0.4.0] - 2026-03-11

### Added

- `ccfm dump` top-level subcommand replacing the old `apply --dump` flag
  - Converts markdown to ADF JSON locally without API calls
  - Supports `--file`, `--directory`, and `--output-dir` options
  - Default output goes to `.ccfm/dumps/<timestamp>_<hash>/` (no more
    scattered `.ccfm-dump-*` directories at project root)
- `ccfm plan` top-level subcommand (split out from `apply`)
  - Supports `--file`, `--directory`, `--plan-exit-code`, and `--force`
- File and directory existence validation with clear error messages for
  `plan`, `apply`, and `dump` subcommands
- Interactive manual test script (`tests/smoke/manual_test.sh`) for
  walking through all CLI test phases
- `MANUAL_TESTING.md` runbook documenting 8 phases of manual smoke tests
- CLI help smoke tests validating all subcommand help output

### Changed

- `plan` and `apply` refactored into separate subcommands sharing a
  common planner module (previously `apply --plan` was the only way to
  preview changes)
- Dump output directory default changed from `.ccfm-dump-<hash>` at
  project root to `.ccfm/dumps/<timestamp>_<hash>/` for cleaner
  workspace organisation

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

[1.0.0]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.5.0...v1.0.0
[0.5.0]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/stevesimpson418/ccfm-convert/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/stevesimpson418/ccfm-convert/releases/tag/v0.1.0
