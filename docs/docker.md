# Docker & CI/CD

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

## CI/CD Pipeline

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

### Deploying docs via GitHub Actions

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
