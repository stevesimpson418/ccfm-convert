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

---

## What's Next?

- **[Syntax Reference](syntax-reference.md)** — Full CCFM syntax with ADF mapping
- **[CLI Reference](cli-reference.md)** — All subcommands, options, and examples
- **[Configuration](configuration.md)** — ccfm.yaml, frontmatter, state management, locking
- **[Deployment Patterns](deployment-patterns.md)** — Single-env, multi-env, multi-source
- **[Docker & CI/CD](docker.md)** — Docker, GitHub Action, pipeline examples
