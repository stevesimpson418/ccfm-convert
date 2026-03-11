# CCFM — Confluence Cloud Flavoured Markdown

A CLI tool that converts Markdown to Atlassian Document Format (ADF) and deploys pages to
Confluence Cloud. Write documentation as Markdown, deploy it as native Confluence pages — no
legacy conversions, no storage format hacks, full editor compatibility.

[![PyPI](https://img.shields.io/pypi/v/ccfm-convert)](https://pypi.org/project/ccfm-convert/)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://github.com/stevesimpson418/ccfm-convert/pkgs/container/ccfm-convert)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: ruff](https://img.shields.io/badge/linting-ruff-red.svg)](https://github.com/astral-sh/ruff)
[![codecov](https://codecov.io/gh/stevesimpson418/ccfm-convert/branch/main/graph/badge.svg)](https://codecov.io/gh/stevesimpson418/ccfm-convert)

- **Native ADF output** — Pages open in the Confluence editor without any legacy conversion
- **Automatic page hierarchy** — Directory structure maps directly to Confluence page hierarchy
- **CCFM extensions** — Status badges, panels, expands, dates, smart page links, emoji, image width control
- **Idempotent** — Safe to run multiple times; creates or updates pages automatically
- **Remote state** — Deployment state stored in Confluence itself, no local files to commit
- **Concurrent deploy protection** — Terraform-style locking prevents conflicting deploys
- **CI/CD ready** — Deploy documentation on every commit to your main branch

Full syntax reference: **[CCFM.md](CCFM.md)**

---

## Quick Start

### 1. Get an API token

Go to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens),
create a token, and note your Atlassian email address.

### 2. Install

```bash
pip install ccfm-convert
```

### 3. Initialise your space

Before deploying for the first time, initialise CCFM in your Confluence space. This creates
a `_ccfm` management page that stores deployment state and lock information.

```bash
ccfm \
  --domain your-domain.atlassian.net \
  --email your.email@example.com \
  --token YOUR_API_TOKEN \
  --space YOUR_SPACE_KEY \
  init
```

This is idempotent — safe to run multiple times. It creates:

- A `_ccfm` container page at the space root
- A `CCFM State Management` child page (tagged with `ccfm-internal` label)

### 4. Write a page

```markdown
---
page_meta:
  title: My First Page
  labels:
    - docs

deploy_config:
  ci_banner: false
---

# My First Page

This is **bold** text, this is *italic*.

> [!info]
> This is an info panel.

::In Progress::blue::   ::Stable::green::
```

### 5. Preview changes

```bash
# See what would change without touching Confluence
ccfm \
  --domain your-domain.atlassian.net \
  --email your.email@example.com \
  --token YOUR_API_TOKEN \
  --space YOUR_SPACE_KEY \
  plan --directory path/to/docs
```

### 6. Apply changes

```bash
# Apply a single file
ccfm \
  --domain your-domain.atlassian.net \
  --email your.email@example.com \
  --token YOUR_API_TOKEN \
  --space YOUR_SPACE_KEY \
  apply --file path/to/my-page.md

# Apply a directory recursively
ccfm \
  --domain your-domain.atlassian.net \
  --email your.email@example.com \
  --token YOUR_API_TOKEN \
  --space YOUR_SPACE_KEY \
  apply --directory path/to/docs

# Skip confirmation prompt (for CI)
ccfm apply --directory docs --auto-approve
```

### 7. Inspect ADF output

Use the `dump` subcommand to convert markdown to ADF JSON files locally without making any
API calls:

```bash
# Dump a single file (auto-creates .ccfm/dumps/<timestamp>/ output directory)
ccfm dump --file path/to/my-page.md

# Dump an entire directory
ccfm dump --directory path/to/docs

# Specify a custom output directory
ccfm dump --directory path/to/docs --output-dir ./adf-output
```

---

## Frontmatter

Every CCFM file should begin with a YAML frontmatter block. Two top-level keys:

```yaml
---
page_meta:
  title: My Page Title
  parent: Architecture Overview   # Optional — overrides directory-based hierarchy
  author: Jane Smith              # Optional — added as an author-* label
  labels:
    - backend
    - api
  attachments:
    - path: diagram.png
      alt: "Architecture diagram"
      width: max                  # Optional width override

deploy_config:
  ci_banner: true                 # Show managed-by-CI banner (default: true)
  ci_banner_text: "Custom text"   # Optional — overrides default banner text
  include_page_metadata: false    # Show metadata expand block (default: false)
  page_status: "current"          # "current" or "draft" (default: current)
  deploy_page: true               # Set to false to skip deployment (default: true)
---
```

See [CCFM.md — Front matter](CCFM.md#front-matter) for the complete field reference.

---

## CLI Reference

CCFM uses subcommands. Global credential options must come **before** the subcommand:

```text
ccfm [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]

Commands:
  init                   Initialise remote state in a Confluence space
  plan                   Preview what would change without making modifications
  apply                  Apply changes to Confluence (add, change, destroy)
  dump                   Convert markdown to ADF JSON files for inspection (no API calls)
  state list             List all pages tracked in remote state
  state pull             Print remote state JSON to stdout
  state push <file>      Overwrite remote state from a local file
  state rm <path>        Remove a page entry from remote state
  state show <path>      Show state entry for a specific path
  lock acquire           Manually acquire the remote lock
  lock status            Show current lock status
  lock release           Force-release a stale lock

Global options (apply to all commands):
  --config PATH          Path to ccfm.yaml config file (default: ccfm.yaml if present)
  --domain DOMAIN        Confluence domain (e.g., company.atlassian.net)
  --email EMAIL          User email address
  --token TOKEN          Atlassian API token (or set CONFLUENCE_TOKEN env var)
  --space SPACE          Space key (e.g., DOCS — not the space display name)
```

### Plan options

```text
ccfm plan [OPTIONS]

Targets (one required):
  --file PATH            Plan for a single markdown file
  --directory PATH       Plan for a directory recursively

Options:
  --docs-root PATH       Documentation root directory (default: docs)
  --git-repo-url URL     Git repo URL for CI banner source links
  --plan-exit-code       Exit 2 when plan detects pending changes (for CI gates)
  --force                Force re-deploy all files regardless of content changes
```

### Apply options

```text
ccfm apply [OPTIONS]

Targets (one required):
  --file PATH            Apply a single markdown file
  --directory PATH       Apply a directory recursively

Options:
  --docs-root PATH       Documentation root directory (default: docs)
  --git-repo-url URL     Git repo URL for CI banner source links
  --auto-approve         Skip confirmation prompt (required for CI/non-interactive use)
  --force                Force re-deploy all files regardless of content changes
  --lock-id ID           Lock identifier for CI traceability (e.g., pipeline ID)
```

### Dump options

```text
ccfm dump [OPTIONS]

Targets (one required):
  --file PATH            Single markdown file to dump
  --directory PATH       Directory to dump (recursive)

Options:
  --docs-root PATH       Root documentation directory (default: docs)
  --git-repo-url URL     Git repo URL for CI banner
  --output-dir PATH      Output directory for .adf.json files (default: .ccfm/dumps/<timestamp>/)
```

No credentials are needed — dump is a local-only operation. The output directory mirrors the
source tree structure (e.g., `docs/team/api.md` becomes `<output-dir>/docs/team/api.adf.json`).

### Examples

```bash
# Initialise CCFM in your space (one-time setup)
ccfm --domain company.atlassian.net --email user@example.com --token abc123 --space DOCS init

# Preview what would change
ccfm --domain company.atlassian.net --email user@example.com --token abc123 --space DOCS \
  plan --directory path/to/docs

# Apply a single file (interactive prompt)
ccfm --domain company.atlassian.net --email user@example.com --token abc123 --space DOCS \
  apply --file path/to/api/authentication.md

# Apply entire docs folder with auto-approve (for CI)
ccfm --domain company.atlassian.net --email user@example.com --token abc123 --space DOCS \
  apply --directory path/to/docs --auto-approve

# With CI banner links back to source files
ccfm --domain company.atlassian.net --email user@example.com --token abc123 --space DOCS \
  apply --directory path/to/docs --git-repo-url "https://github.com/org/repo/blob/main" --auto-approve

# Preview changes (credentials from ccfm.yaml)
ccfm plan --directory docs

# Force re-deploy all files
ccfm apply --directory docs --force --auto-approve

# Check lock status
ccfm --domain company.atlassian.net --email user@example.com --token abc123 --space DOCS \
  lock status

# View tracked pages
ccfm --domain company.atlassian.net --email user@example.com --token abc123 --space DOCS \
  state list
```

---

## State Management

CCFM stores deployment state remotely in Confluence itself — no local state files to commit
or sync. State is stored as a `ccfm-state.json` attachment on the `CCFM State Management`
page, which lives under a `_ccfm` container page in your space.

This enables:

- **Plan mode** — see what would change before applying
- **Change detection** — only deploy files whose content has changed (default behaviour)
- **Destroy detection** — automatically destroy pages whose source files have been deleted
- **No checkin loops** — state changes don't trigger CI rebuilds
- **No merge conflicts** — concurrent deploys don't fight over a state file

### Initialising

Run `ccfm init` before your first apply. This creates the management infrastructure
in your Confluence space:

```bash
ccfm --domain company.atlassian.net --email user@example.com --token abc123 --space DOCS init
```

The command is idempotent — running it again is a no-op. It is a **one-time per-space** operation; you do not need to run it before every apply.

> **Note:** All files inside your `docs_root` directory are managed by CCFM. Removing files or folders will result in destroy operations on the next `ccfm apply`.

### Inspecting and managing state

```bash
# List all tracked pages
ccfm --domain ... --email ... --token ... --space DOCS state list

# Show full details for a specific entry
ccfm --domain ... --email ... --token ... --space DOCS state show docs/my-page.md

# Download the raw state JSON (useful for piping to jq or saving a backup)
ccfm --domain ... --email ... --token ... --space DOCS state pull

# Remove a specific entry (e.g., after manually deleting a page in Confluence)
ccfm --domain ... --email ... --token ... --space DOCS state rm docs/old-page.md
```

#### Recovery: push a repaired state file

If state becomes corrupted, download it, edit it locally, then push it back:

```bash
ccfm --domain ... --email ... --token ... --space DOCS state pull > state-backup.json
# edit state-backup.json
ccfm --domain ... --email ... --token ... --space DOCS state push state-backup.json
```

> **Warning:** `state push` overwrites the remote state completely. Use with caution.

### Plan and apply workflow

Preview what would change without making any modifications:

```bash
ccfm plan --directory docs
```

Apply changes interactively (prompts for confirmation):

```bash
ccfm apply --directory docs
```

Use `--plan-exit-code` with `plan` to exit with code `2` when there are pending changes —
useful for CI gates that block merges until docs are deployed.

Use `--auto-approve` with `apply` to skip the confirmation prompt (required for CI).

---

## Locking

CCFM uses Terraform-style locking to prevent concurrent deploys from corrupting state or
creating duplicate pages. Locks are stored as a content property on the management page,
using Confluence's optimistic concurrency (version numbers) to prevent race conditions.

### How it works

- `ccfm apply` automatically acquires a lock before applying and releases it when done
- If another apply is in progress, the command fails immediately with a lock error
- `ccfm plan` and `ccfm dump` do **not** acquire locks (they're read-only)
- Lock owner is auto-detected as `user@hostname`

### CI traceability

Pass `--lock-id` to associate the lock with a CI pipeline for easier debugging:

```bash
ccfm --space DOCS apply --directory docs --auto-approve --lock-id "$CI_PIPELINE_ID"
```

### Checking lock status

```bash
ccfm --domain ... --email ... --token ... --space DOCS lock status
```

Output shows whether the lock is held, by whom, when it was acquired, and the lock ID.

### Manually acquiring the lock

For maintenance or scripted workflows, acquire the lock without deploying:

```bash
ccfm --domain ... --email ... --token ... --space DOCS lock acquire

# With a custom operation label and lock ID
ccfm --domain ... --email ... --token ... --space DOCS \
  lock acquire --operation maintenance --lock-id "manual-$(date +%s)"
```

### Recovering from stale locks

If a CI job crashes mid-apply, the lock may be left in place. Force-release it:

```bash
ccfm --domain ... --email ... --token ... --space DOCS lock release
```

---

## Config File (ccfm.yaml)

Place a `ccfm.yaml` in your project root to avoid repeating credentials on every run.
CLI arguments always take precedence over config file values.

```yaml
version: 1

domain: company.atlassian.net
email: ${CONFLUENCE_EMAIL}       # env var interpolation supported
token: ${CONFLUENCE_TOKEN}
space: DOCS
docs_root: docs
git_repo_url: https://github.com/org/repo
```

With a config file in place:

```bash
ccfm plan --directory docs
ccfm apply --directory docs --auto-approve
```

**Security note:** `ccfm.yaml` is a trusted-author file. Any environment variable
visible to the process can be interpolated into config values. Review `ccfm.yaml`
changes in pull requests the same way you review CI pipeline changes.

---

## Docker

```bash
docker pull ghcr.io/stevesimpson418/ccfm-convert:latest

docker run --rm \
  -e CONFLUENCE_DOMAIN=company.atlassian.net \
  -e CONFLUENCE_EMAIL=user@example.com \
  -e CONFLUENCE_TOKEN=your-token \
  -v $(pwd)/docs:/docs \
  ghcr.io/stevesimpson418/ccfm-convert:latest \
  apply --space DOCS --directory /docs --auto-approve
```

---

## GitHub Action

```yaml
- uses: stevesimpson418/ccfm-action@v0.1.0
  with:
    domain: ${{ secrets.CONFLUENCE_DOMAIN }}
    email:  ${{ secrets.CONFLUENCE_EMAIL }}
    token:  ${{ secrets.CONFLUENCE_TOKEN }}
    space:  DOCS
    directory: docs
    args: --auto-approve
```

---

## CI/CD

Store credentials as secrets: `CONFLUENCE_DOMAIN`, `CONFLUENCE_EMAIL`, `CONFLUENCE_TOKEN`.

### Pipeline overview

Every PR targeting `main` runs three gates:

| Check | When | Blocks merge? |
| --- | --- | --- |
| Lint + unit tests (100% coverage) | Every push / PR commit | Yes |
| Smoke tests against CCFMDEV space | PRs + pushes touching `src/` or `tests/smoke/` | Yes |
| Markdown lint | Every push / PR commit | Yes |

Smoke tests auto-cleanup Confluence pages after each run. For manual inspection
runs (leave pages in Confluence), use **Actions > Smoke Tests > Run workflow** and
uncheck *Delete Confluence pages after tests*.

Set these required status checks in GitHub > Settings > Branches > main:

- `Lint`, `Test`, `Markdown Lint`, `Smoke Tests (CCFMDEV)`

### Deploying your docs via GitHub Actions

```yaml
name: Deploy Docs

on:
  push:
    branches: [main]
    paths:
      - 'docs/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install ccfm-convert
      - env:
          CONFLUENCE_DOMAIN: ${{ secrets.CONFLUENCE_DOMAIN }}
          CONFLUENCE_EMAIL: ${{ secrets.CONFLUENCE_EMAIL }}
          CONFLUENCE_TOKEN: ${{ secrets.CONFLUENCE_TOKEN }}
        run: |
          # Ensure management page exists (idempotent)
          ccfm \
            --domain "$CONFLUENCE_DOMAIN" \
            --email "$CONFLUENCE_EMAIL" \
            --token "$CONFLUENCE_TOKEN" \
            --space DOCS \
            init

          # Apply with auto-approve and lock ID for CI traceability
          ccfm \
            --domain "$CONFLUENCE_DOMAIN" \
            --email "$CONFLUENCE_EMAIL" \
            --token "$CONFLUENCE_TOKEN" \
            --space DOCS \
            apply \
            --directory docs \
            --git-repo-url "https://github.com/${{ github.repository }}/blob/main" \
            --auto-approve \
            --lock-id "${{ github.run_id }}"
```

---

## Page Hierarchy

Directories map directly to Confluence pages. A file at `docs/Team/Engineering/api.md` creates:

```text
Team
└── Engineering
    └── api
```

By default, container pages (`Team`, `Engineering`) are created as placeholders.
To control a container page's title and content, add a `.page_content.md` file inside the directory:

```text
docs/
└── Team/
    ├── .page_content.md    ← controls the "Team" Confluence page
    └── Engineering/
        ├── .page_content.md
        └── api.md
```

`.page_content.md` files support full CCFM syntax and frontmatter, including labels and
custom titles.

---

## Project Structure

```text
.
├── src/
│   └── ccfm_convert/
│       ├── adf/                  # Markdown → ADF converter (pure, no I/O)
│       │   ├── nodes.py          # ADF node constructor functions
│       │   ├── inline.py         # Inline markdown parsing
│       │   ├── blocks.py         # Block markdown parsing
│       │   └── converter.py      # Orchestration; convert() entry point
│       ├── deploy/               # Confluence API and deployment logic
│       │   ├── api.py            # ConfluenceAPI class (REST v2 + v1 for attachments/properties)
│       │   ├── frontmatter.py    # YAML frontmatter parsing
│       │   ├── orchestration.py  # deploy_page(), deploy_tree(), destroy_page()
│       │   └── transforms.py     # CI banner, page link resolution, attachment media nodes
│       ├── state/                # Remote state and locking
│       │   ├── backend.py        # StateBackend protocol + ConfluenceBackend
│       │   ├── manager.py        # StateManager — filepath → page_id mapping, content hashing
│       │   ├── lock.py           # LockManager — Terraform-style deploy locking
│       │   └── init.py           # init_remote_state() — one-time space setup
│       ├── config/               # Project config file loader
│       │   └── loader.py         # ccfm.yaml loader with ${ENV_VAR} interpolation
│       ├── plan/                 # Plan/diff mode
│       │   └── planner.py        # compute_plan(), DeployPlan — terraform-style diff output
│       └── main.py               # CLI entry point (argparse subcommands)
├── tests/
│   ├── smoke/                # End-to-end smoke tests (real Confluence space)
│   │   ├── conftest.py       # Credentials, cleanup hook, ccfm_run fixture
│   │   ├── docs/             # Fixture markdown files deployed during smoke tests
│   │   └── test_*.py         # Smoke test modules
│   └── test_*.py             # Unit tests (100% coverage, all mocked)
├── ccfm.yaml                 # Optional project config (credentials, space, docs_root)
├── CCFM.md                   # Complete CCFM syntax and ADF mapping reference
├── requirements.txt          # Runtime dependencies
├── requirements-test.txt     # Development and test dependencies
└── pyproject.toml            # Toolchain configuration (black, ruff, pytest, coverage)
```

---

## Development

### Setup

```bash
python -m venv .env
source .env/bin/activate    # Windows: .env\Scripts\activate

# Install the package and dev/test dependencies
pip install -e .
pip install -r requirements-test.txt

# Install pre-commit hooks
pre-commit install
```

### Running tests

```bash
pytest                              # All unit tests with coverage report
pytest tests/test_converter.py      # Single file
pytest -k "test_heading"            # Single test by name
```

Coverage runs automatically via `pyproject.toml`. The target is 100% line coverage on `src/`.

### Smoke tests

End-to-end tests that deploy real pages to a Confluence space. Requires credentials for a
dedicated test space (the project uses `CCFMDEV` at `ccfm.atlassian.net`).

```bash
# Copy and fill in credentials
cp .env.smoke.example .env.smoke
# Edit .env.smoke with your values, then:
source .env.smoke

# Run all smoke tests and auto-cleanup Confluence pages when done
pytest tests/smoke/ --no-cov -v

# Run tests and leave pages in Confluence for manual inspection
pytest tests/smoke/ --no-cov -v --no-cleanup

# Delete pages from a previous --no-cleanup run (skips re-running tests)
pytest tests/smoke/ --no-cov -v --cleanup-only
```

**GitHub Actions:** Go to Actions > Smoke Tests > Run workflow (manual trigger).
Requires `CONFLUENCE_DOMAIN`, `CONFLUENCE_EMAIL`, and `CONFLUENCE_TOKEN` secrets.
Uncheck "Delete Confluence pages after tests" to leave pages for manual inspection.

### Code style

- **Formatter**: Black (line length 100)
- **Linter**: Ruff
- **Python**: 3.12

```bash
black src/                  # Format
ruff check src/             # Lint
pre-commit run --all-files  # All hooks
```

---

## Architecture

### `src/ccfm_convert/adf/` — Pure conversion

No I/O, no network calls. Entry point: `convert(markdown: str) -> dict`.

- `nodes.py` — ADF node constructor functions (`doc()`, `heading()`, `paragraph()`, etc.)
- `inline.py` — Inline parsing: bold, italic, code, links, emoji, status badges, dates
- `blocks.py` — Block parsing: tables, lists (bullet/ordered/task), panels, expands, blockquotes
- `converter.py` — Orchestrates the conversion; calls into blocks and inline parsers

### `src/ccfm_convert/deploy/` — Confluence API interaction

- `api.py` — `ConfluenceAPI` class wrapping REST API v2 (v1 for attachment upload —
  Confluence v2 lacks a POST attachment endpoint, tracked at CONFCLOUD-77196)
- `frontmatter.py` — `parse_frontmatter(content) -> (metadata, markdown)` strips and parses YAML
- `orchestration.py` — `deploy_page()`, `deploy_tree()`, `ensure_page_hierarchy()` coordinate
  the full deploy flow
- `transforms.py` — Post-conversion ADF mutations: CI banner injection, internal page link
  resolution, attachment media node rewriting

### `src/ccfm_convert/state/` — Remote state and locking

- `backend.py` — `StateBackend` protocol with `load()`/`save()` methods;
  `ConfluenceBackend` stores state as a JSON attachment on the management page
- `manager.py` — `StateManager` tracks deployed pages, computes content hashes,
  detects orphaned pages. Backend-agnostic via `StateBackend` protocol
- `lock.py` — `LockManager` implements Terraform-style locking using Confluence content
  properties with optimistic concurrency (409 Conflict = race condition)
- `init.py` — `init_remote_state()` creates the `_ccfm` management infrastructure

### Attachment upload flow

Confluence's v2 API lacks an attachment POST endpoint, so the deploy tool uses a multi-step
workaround:

1. Create or update the page (attachment media nodes are placeholders at this point)
2. Upload attachments via v1 API (`/rest/api/content/{id}/child/attachment`)
3. Fetch the Media Services `fileId` (UUID) via v2 API GET — the v1 upload response does not
   include it
4. Re-update the page with correct ADF `media` nodes containing the real `fileId` and `collection`

---

## Troubleshooting

**Authentication failed**
Verify the token is correct and the email matches your Atlassian account. Ensure you have
create/edit permissions in the target space.

**Space not found**
Use the space **key** (e.g., `DOCS`), not the display name. The key appears in the URL:
`/wiki/spaces/DOCS/`.

**"Run `ccfm init` first"**
The management page was not found in your space. Run `ccfm init` to create the `_ccfm`
container and state management page.

**Apply blocked by lock**
Another apply is in progress (or a previous apply crashed without releasing the lock).
Check the lock status and force-release if the lock is stale:

```bash
ccfm --domain ... --email ... --token ... --space DOCS lock status
ccfm --domain ... --email ... --token ... --space DOCS lock release
```

**Image not rendering after redeploy**
The Confluence v1 attachment update endpoint returns a different response shape than the create
endpoint. CCFM normalises this automatically — ensure you are running the latest version.

**Page hierarchy issues**
Ensure markdown files are under the directory passed to `--directory`. Directories without
`.page_content.md` get an auto-generated placeholder page. Add one to control the container
page's title and content.

**Debugging ADF output**
Use `ccfm dump` to write `.adf.json` files to a dedicated output directory. Inspect these to
verify the ADF structure before deploying to Confluence.

---

## Contributing

1. Fork the repository and create a feature branch
2. Run `pre-commit install` to set up hooks
3. Make your changes
4. Run `pytest` — all tests must pass, coverage must be maintained
5. Run `pre-commit run --all-files`
6. Submit a pull request

---

## Credits

Built on:

- [Confluence Cloud REST API v2](https://developer.atlassian.com/cloud/confluence/rest/v2/)
- [Atlassian Document Format](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/)
- [PyYAML](https://pyyaml.org/) · [Requests](https://requests.readthedocs.io/)
