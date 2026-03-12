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
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://stevesimpson418.github.io/ccfm-convert/)

- **Native ADF output** — Pages open in the Confluence editor without any legacy conversion
- **Automatic page hierarchy** — Directory structure maps directly to Confluence page hierarchy
- **CCFM extensions** — Status badges, panels, expands, dates, smart page links, emoji, image width control
- **Idempotent** — Safe to run multiple times; creates or updates pages automatically
- **Remote state** — Deployment state stored in Confluence itself, no local files to commit
- **Concurrent deploy protection** — Terraform-style locking prevents conflicting deploys
- **CI/CD ready** — Deploy documentation on every commit to your main branch

**[Full documentation](https://stevesimpson418.github.io/ccfm-convert/)** |
**[Syntax reference](CCFM.md)**

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

```bash
ccfm \
  --domain your-domain.atlassian.net \
  --email your.email@example.com \
  --token YOUR_API_TOKEN \
  --space YOUR_SPACE_KEY \
  init
```

This is idempotent — safe to run multiple times. It creates the `_ccfm` management
infrastructure that stores deployment state and lock information.

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
ccfm plan --directory path/to/docs
ccfm apply --directory path/to/docs --auto-approve
```

For the full CLI reference, configuration options, and deployment patterns, see the
[documentation site](https://stevesimpson418.github.io/ccfm-convert/).

---

## Page Hierarchy

Directories map directly to Confluence pages. A file at `docs/Team/Engineering/api.md` creates:

```text
Team
└── Engineering
    └── api
```

To control a container page's title and content, add a `.page_content.md` file inside the directory.

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

For GitHub Action usage and CI/CD pipeline examples, see
[Docker & CI/CD](https://stevesimpson418.github.io/ccfm-convert/docker/).

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

End-to-end tests that deploy real pages to a Confluence space:

```bash
cp .env.smoke.example .env.smoke
# Edit .env.smoke with your values, then:
source .env.smoke
pytest tests/smoke/ --no-cov -v
```

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
