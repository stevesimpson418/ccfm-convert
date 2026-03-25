# Deployment Patterns

CCFM supports several deployment patterns depending on your team structure and documentation needs.

---

## Pattern 1: Single Environment

The simplest setup — one repository, one Confluence space.

```text
repo/
└── docs/
    ├── getting-started.md
    ├── api-reference.md
    └── guides/
        ├── .page_content.md
        └── deployment.md
```

```yaml
# ccfm.yaml
version: 1
domain: company.atlassian.net
email: ${CONFLUENCE_EMAIL}
token: ${CONFLUENCE_TOKEN}
space: DOCS
docs_root: docs
```

```bash
ccfm plan
ccfm apply --auto-approve
```

**Best for:** Small teams, single product documentation, internal tooling docs.

---

## Pattern 2: Multi-Environment

Deploy the same docs to different Confluence spaces (e.g., staging and production) using
separate config files or environment variables.

```bash
# Deploy to staging
CONFLUENCE_DOMAIN=staging.atlassian.net \
CONFLUENCE_TOKEN=$STAGING_TOKEN \
ccfm --config ccfm-staging.yaml apply --auto-approve

# Deploy to production
CONFLUENCE_DOMAIN=company.atlassian.net \
CONFLUENCE_TOKEN=$PROD_TOKEN \
ccfm --config ccfm-prod.yaml apply --auto-approve
```

Or use separate config files:

```bash
ccfm --config ccfm-staging.yaml apply --auto-approve
ccfm --config ccfm-prod.yaml apply --auto-approve
```

**Best for:** Teams that want to review docs in a staging space before publishing to production.

---

## Pattern 3: Multi-Source

Two (or more) documentation trees in one repository, each synced to a **different Confluence space**
using its own CCFM config file.

```text
repo/
├── ccfm-api.yaml         # Config targeting ENG space
├── ccfm-wiki.yaml        # Config targeting WIKI space
├── docs/                 # API documentation
│   ├── getting-started.md
│   └── endpoints.md
└── docs-wiki/            # Team wiki pages
    ├── runbooks.md
    └── onboarding.md
```

Each config points at a different `docs_root` and `space`:

```yaml
# ccfm-api.yaml
version: 1
domain: company.atlassian.net
email: ${CONFLUENCE_EMAIL}
token: ${CONFLUENCE_TOKEN}
space: ENG
docs_root: docs
```

```yaml
# ccfm-wiki.yaml
version: 1
domain: company.atlassian.net
email: ${CONFLUENCE_EMAIL}
token: ${CONFLUENCE_TOKEN}
space: WIKI
docs_root: docs-wiki
```

Deploy each source independently:

```bash
ccfm --config ccfm-api.yaml plan
ccfm --config ccfm-api.yaml apply --auto-approve

ccfm --config ccfm-wiki.yaml plan
ccfm --config ccfm-wiki.yaml apply --auto-approve
```

**Best for:** Repos that own documentation across multiple Confluence spaces — e.g., API docs
in an engineering space and team runbooks in an internal wiki space.

See the full working example in the
[ccfm-examples/standalone/multi-source](https://github.com/stevesimpson418/ccfm-examples/tree/main/standalone/multi-source)
directory.

---

## Examples Repository

For complete working examples of these patterns with CI/CD configurations, see the
[ccfm-examples](https://github.com/stevesimpson418/ccfm-examples) repository.
