# CCFM — Confluence Cloud Flavoured Markdown

A CLI tool that converts Markdown to Atlassian Document Format (ADF) and deploys pages to
Confluence Cloud. Write documentation as Markdown, deploy it as native Confluence pages — no
legacy conversions, no storage format hacks, full editor compatibility.

[![PyPI](https://img.shields.io/pypi/v/ccfm-convert)](https://pypi.org/project/ccfm-convert/)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://github.com/stevesimpson418/ccfm-convert/pkgs/container/ccfm-convert)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)

## Features

- **Native ADF output** — Pages open in the Confluence editor without any legacy conversion
- **Automatic page hierarchy** — Directory structure maps directly to Confluence page hierarchy
- **CCFM extensions** — Status badges, panels, expands, dates, smart page links, emoji, image width control
- **Idempotent** — Safe to run multiple times; creates or updates pages automatically
- **Remote state** — Deployment state stored in Confluence itself, no local files to commit
- **Concurrent deploy protection** — Terraform-style locking prevents conflicting deploys
- **CI/CD ready** — Deploy documentation on every commit to your main branch

Full syntax reference: **[CCFM Syntax Reference](syntax-reference.md)**

---

## Design Philosophy

Each Confluence space is managed by exactly one `ccfm.yaml` configuration. That configuration
defines the `docs_root` — the single directory whose contents are deployed to the space. All
files under `docs_root` are deployed, and the directory structure maps directly to the
Confluence page hierarchy.

This is the foundation of CCFM's state model. Deployment state is stored per-space, so reliable
change detection, orphan cleanup, and locking all depend on a single configuration owning each
space. If two configurations deploy to the same space, each one sees the other's pages as
orphans and will plan to destroy them.

A single repository can manage multiple Confluence spaces — use a separate `ccfm.yaml` for each
space, each with its own `docs_root`. This is safe because each space has its own independent
state. See [Deployment Patterns](deployment-patterns.md) for examples.

!!! warning "Never deploy to the same space from multiple repositories"
    Each space must have exactly one managing configuration. Deploying to the same Confluence
    space from multiple repositories (or multiple configs targeting the same space) will cause
    state conflicts — orphan detection will destroy pages it doesn't recognise.

### Why one config per space?

CCFM tracks deployment state per space — which pages exist, their content hashes, and when they
were last deployed. Orphan detection compares this state against the files in your `docs_root`
to determine what should be created, updated, or destroyed. This only works when a single
configuration owns the space's state.

This is the same constraint that Terraform and other state-based infrastructure tools enforce:
each state backend should be managed by exactly one configuration. When two configurations share
state, each one sees the other's managed resources as orphans and plans to destroy them.

If following best practices, CCFM docs live in version control. If pages are accidentally
destroyed, recovery is a re-deploy from the source files — no data is lost, just temporarily
unavailable.

The `plan` command always shows pending destroy actions before any changes are applied, and
`apply` requires explicit confirmation (or `--auto-approve` for CI). These guardrails give
you visibility before any destructive action is taken.

### Best practices: store documentation in version control

While CCFM can deploy markdown files from any local directory, we strongly recommend storing
your documentation in a version control system such as Git. This enables:

- **Recovery** — if pages are accidentally destroyed or overwritten, restore from history and
  re-deploy
- **Review** — documentation changes go through the same review process as code (pull requests,
  merge requests)
- **Audit trail** — full history of who changed what and when
- **CI/CD integration** — automate deployments on merge to your main branch, ensuring Confluence
  stays in sync with the source
- **Collaboration** — multiple authors can work on documentation concurrently using branches
  without conflicting

---

## Quick Start

### 1. Get an API token

Go to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens),
create a token, and note your Atlassian email address.

### 2. Install

```bash
pip install ccfm-convert
```

Or use Docker:

```bash
docker pull ghcr.io/stevesimpson418/ccfm-convert:latest
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

This is idempotent — safe to run multiple times.

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

### 5. Preview and apply

```bash
# See what would change without touching Confluence
ccfm plan

# Apply changes (interactive confirmation)
ccfm apply

# Skip confirmation prompt (for CI)
ccfm apply --auto-approve
```

### 6. Inspect ADF output

Use `--debug-file` to convert a single markdown file to ADF JSON and print it to stdout
without making any API calls:

```bash
ccfm plan --debug-file path/to/my-page.md
ccfm plan --debug-file path/to/my-page.md | jq '.content[0]'
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

### Container pages and page links

Container pages (created from `.page_content.md`) are deployed **before** their child pages.
If a `.page_content.md` contains page links to its own children (e.g., `[Overview](<Team Overview>)`),
those links cannot resolve on the first deploy because the child pages don't exist yet.

**Workaround:** Run `ccfm apply --force --auto-approve` after the initial deploy to re-push
all pages — the child pages now exist and the links will resolve correctly.

**Recommended alternative:** Instead of manually linking to child pages from a container page,
use Confluence's built-in **Children Display macro** after the initial deploy. This macro
automatically lists all child pages and stays up to date as pages are added or removed — no
manual link maintenance required. Since the macro is added via the Confluence editor (not the
markdown source), it won't be overwritten by subsequent CCFM deploys.

---

## FAQ

### Multiple teams need to publish documentation — what's the best approach?

**Option A: Centralised docs repo with team-owned subdirectories.** One repository, one
Confluence space. Each team owns a directory:

```text
docs/
├── auth-team/
├── payments-team/
└── platform-team/
```

This is the simplest model — one deploy pipeline, one state, clear hierarchy.

**Option B: Separate Confluence spaces per team.** Each team has their own repository
and their own Confluence space. Use a GitLab/GitHub group or org to keep docs repos
discoverable. Consider a repo template so new teams can bootstrap quickly with CI
pipelines, linting, and CCFM config pre-configured.

### Can I deploy from multiple repositories to the same Confluence space?

No. Each Confluence space must be managed by exactly one `ccfm.yaml` configuration. Deploying
from a second configuration will cause orphan detection to destroy pages created by the first.

If multiple teams need to contribute to the same space, use a single repository with
team-owned subdirectories under one `docs_root`.

### Can I manage multiple Confluence spaces from one repository?

Yes. Create a separate `ccfm.yaml` for each space, each with its own `docs_root` directory.
Each space has independent state, so there is no conflict. See
[Deployment Patterns — Multi-Source](deployment-patterns.md#pattern-3-multi-source) for a
worked example.

### Can I use CCFM without a config file?

For `plan --debug-file` (ADF inspection), yes — no config or credentials needed. For `plan`
and `apply`, you need a `ccfm.yaml` with at least `docs_root` configured. Credentials can come
from the config file, CLI flags, or environment variables.

---

## What's Next?

- **[Syntax Reference](syntax-reference.md)** — Full CCFM syntax with ADF mapping
- **[CLI Reference](cli-reference.md)** — All subcommands, options, and examples
- **[Configuration](configuration.md)** — ccfm.yaml, frontmatter, state management, locking
- **[Deployment Patterns](deployment-patterns.md)** — Single-env, multi-env, multi-source
- **[Docker & CI/CD](docker.md)** — Docker, GitHub Action, pipeline examples
