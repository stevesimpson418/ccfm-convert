# Architecture

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
│       │   ├── dependencies.py   # Dependency graph resolution and topological ordering
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

## `src/ccfm_convert/adf/` — Pure Conversion

No I/O, no network calls. Entry point: `convert(markdown: str) -> dict`.

- **`nodes.py`** — ADF node constructor functions (`doc()`, `heading()`, `paragraph()`, etc.)
- **`inline.py`** — Inline parsing: bold, italic, code, links, emoji, status badges, dates
- **`blocks.py`** — Block parsing: tables, lists (bullet/ordered/task), panels, expands, blockquotes
- **`converter.py`** — Orchestrates the conversion; calls into blocks and inline parsers

## `src/ccfm_convert/deploy/` — Confluence API Interaction

- **`api.py`** — `ConfluenceAPI` class wrapping REST API v2 (v1 for attachment upload —
  Confluence v2 lacks a POST attachment endpoint, tracked at CONFCLOUD-77196)
- **`frontmatter.py`** — `parse_frontmatter(content) -> (metadata, markdown)` strips and parses YAML
- **`orchestration.py`** — `deploy_page()`, `deploy_tree()`, `ensure_page_hierarchy()` coordinate
  the full deploy flow
- **`transforms.py`** — Post-conversion ADF mutations: CI banner injection, internal page link
  resolution, attachment media node rewriting
- **`dependencies.py`** — Dependency graph resolution for deployment ordering. Scans markdown
  files for `[text](<Page Title>)` links, builds a directed graph, and topologically sorts
  to ensure linked pages deploy before pages that reference them

## `src/ccfm_convert/state/` — Remote State and Locking

- **`backend.py`** — `StateBackend` protocol with `load()`/`save()` methods;
  `ConfluenceBackend` stores state as a JSON attachment on the management page
- **`manager.py`** — `StateManager` tracks deployed pages, computes content hashes,
  detects orphaned pages. Backend-agnostic via `StateBackend` protocol
- **`lock.py`** — `LockManager` implements Terraform-style locking using Confluence content
  properties with optimistic concurrency (409 Conflict = race condition)
- **`init.py`** — `init_remote_state()` creates the `_ccfm` management infrastructure

---

## Attachment Upload Flow

Confluence's v2 API lacks an attachment POST endpoint, so the deploy tool uses a multi-step
workaround:

1. Create or update the page (attachment media nodes are placeholders at this point)
2. Upload attachments via v1 API (`/rest/api/content/{id}/child/attachment`)
3. Fetch the Media Services `fileId` (UUID) via v2 API GET — the v1 upload response does not
   include it
4. Re-update the page with correct ADF `media` nodes containing the real `fileId` and `collection`

---

## Dependency-Ordered Deployment

When deploying a directory, CCFM analyses internal page links (`[text](<Page Title>)`) to
determine deployment order. Pages that are linked to are deployed **before** pages that
reference them, ensuring links resolve correctly on first deploy.

### How It Works

1. **Scan** — Each markdown file is scanned for `[text](<Page Title>)` patterns
2. **Title mapping** — Frontmatter titles (or filename-derived titles) are mapped to file paths
3. **Graph build** — A directed dependency graph is constructed (A → B means A depends on B)
4. **Topological sort** — Kahn's algorithm produces a deployment order where dependencies come first
5. **Cycle detection** — Circular dependencies are detected, warned about, and broken by falling
   back to alphabetical file order for cycle participants

### Scope

Dependency ordering only considers pages **within the current deployment set** (files under
docs root). Links to pre-existing Confluence pages that are not managed by CCFM resolve via
the Confluence API at deploy time and do not affect ordering.

**Known limitation:** Cross-space page links are not supported. The `[text](<Page Title>)`
syntax resolves titles within the target space only.

### `--auto-deploy-deps`

When deploying a single file with `--file`, linked pages are not automatically deployed.
Add `--auto-deploy-deps` to discover and deploy dependency pages from the docs root:

```bash
ccfm apply --file docs/team/overview.md --auto-deploy-deps --docs-root docs
```

This scans `docs/` for files whose titles match the linked page titles, resolves transitive
dependencies, and deploys them all in the correct order. If a linked title cannot be mapped
to a local file, a warning is printed and deployment continues.
