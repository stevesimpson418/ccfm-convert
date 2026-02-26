# CCFM — Confluence Cloud Flavoured Markdown

A CLI tool that converts Markdown to Atlassian Document Format (ADF) and deploys pages to
Confluence Cloud. Write documentation as Markdown, deploy it as native Confluence pages — no
legacy conversions, no storage format hacks, full editor compatibility.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: ruff](https://img.shields.io/badge/linting-ruff-red.svg)](https://github.com/astral-sh/ruff)
[![codecov](https://codecov.io/gh/stevesimpson418/ccfm-convert/branch/main/graph/badge.svg)](https://codecov.io/gh/stevesimpson418/ccfm-convert)

- **Native ADF output** — Pages open in the Confluence editor without any legacy conversion
- **Automatic page hierarchy** — Directory structure maps directly to Confluence page hierarchy
- **CCFM extensions** — Status badges, panels, expands, dates, smart page links, emoji, image width control
- **Idempotent** — Safe to run multiple times; creates or updates pages automatically
- **CI/CD ready** — Deploy documentation on every commit to your main branch

Full syntax reference: **[CCFM.md](CCFM.md)**

---

## Quick Start

### 1. Get an API token

Go to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens),
create a token, and note your Atlassian email address.

### 2. Install

```bash
python -m venv .env
source .env/bin/activate    # Windows: .env\Scripts\activate

pip install -r requirements.txt
```

### 3. Write a page

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

### 4. Deploy

```bash
# Deploy a single file
python src/main.py \
  --domain your-domain.atlassian.net \
  --email your.email@example.com \
  --token YOUR_API_TOKEN \
  --space YOUR_SPACE_KEY \
  --file path/to/my-page.md

# Deploy a directory recursively
python src/main.py \
  --domain your-domain.atlassian.net \
  --email your.email@example.com \
  --token YOUR_API_TOKEN \
  --space YOUR_SPACE_KEY \
  --directory path/to/docs
```

### 5. Inspect before deploying

Use `--dump` to write ADF JSON files locally without making any API calls:

```bash
python src/main.py \
  --domain your-domain.atlassian.net \
  --email your.email@example.com \
  --token YOUR_API_TOKEN \
  --space YOUR_SPACE_KEY \
  --file path/to/my-page.md \
  --dump
# Writes path/to/my-page.adf.json for inspection
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

```text
python src/main.py [OPTIONS]

Required (not needed for --plan or --dump):
  --domain DOMAIN          Confluence domain (e.g., company.atlassian.net)
  --email EMAIL            User email address
  --token TOKEN            Atlassian API token (or set CONFLUENCE_TOKEN env var)
  --space SPACE            Space key (e.g., DOCS — not the space display name)

Deployment targets (one required):
  --file PATH              Deploy a single markdown file
  --directory PATH         Deploy a directory recursively

Options:
  --config PATH            Path to ccfm.yaml config file (default: ccfm.yaml if present)
  --state PATH             Path to state file (default: .ccfm-state.json)
  --docs-root PATH         Documentation root directory (default: docs)
  --git-repo-url URL       Git repo URL for CI banner source links
  --dump                   Write ADF to .adf.json files, skip deployment
  --plan                   Show what would be deployed without making any changes
  --changed-only           Only deploy files whose content has changed since last deploy
  --archive-orphans        Archive Confluence pages for markdown files removed from disk
```

### Examples

```bash
# Deploy a single file
python src/main.py \
  --domain company.atlassian.net \
  --email user@example.com \
  --token abc123 \
  --space DOCS \
  --file path/to/api/authentication.md

# Deploy entire docs folder
python src/main.py \
  --domain company.atlassian.net \
  --email user@example.com \
  --token abc123 \
  --space DOCS \
  --directory path/to/docs

# With CI banner links back to source files
python src/main.py \
  --domain company.atlassian.net \
  --email user@example.com \
  --token abc123 \
  --space DOCS \
  --directory path/to/docs \
  --git-repo-url "https://github.com/org/repo/blob/main"
```

---

## State Management

CCFM tracks deployed pages in a local `.ccfm-state.json` file. This enables:

- **Plan mode** — see what would change before deploying
- **Changed-only deploys** — skip files with no content changes (faster CI)
- **Orphan archiving** — archive pages whose source files have been deleted

**Commit the state file** alongside your documentation. Team members and CI pipelines
share the same deployment history through version control.

```bash
# Preview what would be deployed (no API calls made)
python src/main.py \
  --domain company.atlassian.net \
  --email user@example.com \
  --token abc123 \
  --space DOCS \
  --directory docs \
  --plan

# Only deploy changed files (faster CI runs)
python src/main.py \
  --domain company.atlassian.net \
  --email user@example.com \
  --token abc123 \
  --space DOCS \
  --directory docs \
  --changed-only

# Archive pages whose source markdown files were deleted
python src/main.py \
  --domain company.atlassian.net \
  --email user@example.com \
  --token abc123 \
  --space DOCS \
  --directory docs \
  --archive-orphans
```

`--plan` exits with code `2` when there are pending changes and `0` when everything is
up to date — useful for CI gates.

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
state_file: .ccfm-state.json
```

With a config file in place:

```bash
python src/main.py --directory docs --plan
python src/main.py --directory docs
```

**Security note:** `ccfm.yaml` is a trusted-author file. Any environment variable
visible to the process can be interpolated into config values. Review `ccfm.yaml`
changes in pull requests the same way you review CI pipeline changes.

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

## CI/CD

Store credentials as secrets: `CONFLUENCE_DOMAIN`, `CONFLUENCE_EMAIL`, `CONFLUENCE_TOKEN`.

### GitHub Actions

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
      - run: pip install -r requirements.txt
      - env:
          CONFLUENCE_DOMAIN: ${{ secrets.CONFLUENCE_DOMAIN }}
          CONFLUENCE_EMAIL: ${{ secrets.CONFLUENCE_EMAIL }}
          CONFLUENCE_TOKEN: ${{ secrets.CONFLUENCE_TOKEN }}
        run: |
          python src/main.py \
            --domain "$CONFLUENCE_DOMAIN" \
            --email "$CONFLUENCE_EMAIL" \
            --token "$CONFLUENCE_TOKEN" \
            --space DOCS \
            --directory docs \
            --git-repo-url "https://github.com/${{ github.repository }}/blob/main" \
            --changed-only
```

---

## Project Structure

```text
.
├── src/
│   ├── adf/                  # Markdown → ADF converter (pure, no I/O)
│   │   ├── nodes.py          # ADF node constructor functions
│   │   ├── inline.py         # Inline markdown parsing
│   │   ├── blocks.py         # Block markdown parsing
│   │   └── converter.py      # Orchestration; convert() entry point
│   ├── deploy/               # Confluence API and deployment logic
│   │   ├── api.py            # ConfluenceAPI class (REST v2 + v1 for attachments)
│   │   ├── frontmatter.py    # YAML frontmatter parsing
│   │   ├── orchestration.py  # deploy_page(), deploy_tree(), archive_page()
│   │   └── transforms.py     # CI banner, page link resolution, attachment media nodes
│   ├── state/                # Deployment state persistence
│   │   └── manager.py        # StateManager — filepath → page_id mapping, content hashing
│   ├── config/               # Project config file loader
│   │   └── loader.py         # ccfm.yaml loader with ${ENV_VAR} interpolation
│   ├── plan/                 # Plan/diff mode
│   │   └── planner.py        # compute_plan(), DeployPlan — terraform-style diff output
│   └── main.py               # CLI entry point (argparse)
├── tests/
│   ├── smoke/                # End-to-end smoke tests (real Confluence space)
│   │   ├── conftest.py       # Credentials, cleanup hook, ccfm_run fixture
│   │   ├── docs/             # Fixture markdown files deployed during smoke tests
│   │   └── test_*.py         # Smoke test modules
│   └── test_*.py             # Unit tests (100% coverage, all mocked)
├── .ccfm-state.json          # Deployment state (commit this alongside your docs)
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

# Install runtime and dev/test dependencies
pip install -r requirements.txt -r requirements-test.txt

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
cp .env.smoke.example .env
# Edit .env with your values, then:
source .env

# Run all smoke tests and auto-cleanup Confluence pages when done
pytest tests/smoke/ --no-cov -v

# Run tests and leave pages in Confluence for manual inspection
pytest tests/smoke/ --no-cov -v --no-cleanup

# Delete pages from a previous --no-cleanup run (skips re-running tests)
pytest tests/smoke/ --no-cov -v --cleanup-only
```

**GitHub Actions:** Go to Actions → Smoke Tests → Run workflow (manual trigger).
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

### `src/adf/` — Pure conversion

No I/O, no network calls. Entry point: `convert(markdown: str) -> dict`.

- `nodes.py` — ADF node constructor functions (`doc()`, `heading()`, `paragraph()`, etc.)
- `inline.py` — Inline parsing: bold, italic, code, links, emoji, status badges, dates
- `blocks.py` — Block parsing: tables, lists (bullet/ordered/task), panels, expands, blockquotes
- `converter.py` — Orchestrates the conversion; calls into blocks and inline parsers

### `src/deploy/` — Confluence API interaction

- `api.py` — `ConfluenceAPI` class wrapping REST API v2 (v1 for attachment upload —
  Confluence v2 lacks a POST attachment endpoint, tracked at CONFCLOUD-77196)
- `frontmatter.py` — `parse_frontmatter(content) -> (metadata, markdown)` strips and parses YAML
- `orchestration.py` — `deploy_page()`, `deploy_tree()`, `ensure_page_hierarchy()` coordinate
  the full deploy flow
- `transforms.py` — Post-conversion ADF mutations: CI banner injection, internal page link
  resolution, attachment media node rewriting

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

**Image not rendering after redeploy**
The Confluence v1 attachment update endpoint returns a different response shape than the create
endpoint. CCFM normalises this automatically — ensure you are running the latest version.

**Page hierarchy issues**
Ensure markdown files are under the directory passed to `--directory`. Directories without
`.page_content.md` get an auto-generated placeholder page. Add one to control the container
page's title and content.

**Debugging ADF output**
Use `--dump` to write `.adf.json` files alongside each markdown file. Inspect these to verify
the ADF structure before deploying to Confluence.

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
