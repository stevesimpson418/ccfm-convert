# Configuration

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
ci_banner: true                  # Show CI banner on all pages (default: true)
ci_banner_text: "Custom banner"  # Optional — overrides default banner text
```

### ci_banner (optional)

Set `ci_banner: false` in `ccfm.yaml` to disable the CI banner across every page in the
project without needing to add `ci_banner: false` to each file's frontmatter. Per-page
frontmatter still wins — a file with `deploy_config.ci_banner: true` will keep its banner
even when the global toggle is off.

Precedence (highest first):

1. Per-page frontmatter `deploy_config.ci_banner`
2. CLI flags `--ci-banner` / `--no-ci-banner`
3. Global `ci_banner` in `ccfm.yaml`
4. Default (`true`)

### docs_root (required)

The `docs_root` key defines the root directory that CCFM manages. All files under this
directory are deployed to Confluence, and removing files triggers destroy operations.

`docs_root` must be explicitly configured in `ccfm.yaml` — there is no default and no CLI
flag. If not set, ccfm exits with a clear error. This prevents accidental deployment of the
wrong directory.

With a config file in place, you can run commands without any target flags:

```bash
ccfm plan
ccfm apply --auto-approve
```

!!! warning "Security note"
    `ccfm.yaml` is a trusted-author file. Any environment variable visible to the process
    can be interpolated into config values. Review `ccfm.yaml` changes in pull requests the
    same way you review CI pipeline changes.

---

## Frontmatter

Every CCFM file should begin with a YAML frontmatter block. Two top-level keys:

```yaml
---
page_meta:
  title: My Page Title
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

!!! note
    Setting `deploy_page: false` on a previously deployed page will **destroy** that page
    on the next `apply`. If every child page under a directory container has `deploy_page: false`,
    the container page itself is also destroyed. This lets you remove pages from Confluence without
    deleting the source file from your repository.

See [CCFM Syntax Reference — Front matter](syntax-reference.md#front-matter) for the complete
field reference.

---

## Environment Variables

Credentials can be provided via environment variables instead of CLI flags or config file:

| Variable | Description |
| --- | --- |
| `CONFLUENCE_DOMAIN` | Confluence domain (e.g., `company.atlassian.net`) |
| `CONFLUENCE_EMAIL` | User email address |
| `CONFLUENCE_TOKEN` | Atlassian API token |

The `ccfm.yaml` config file supports `${ENV_VAR}` interpolation, so you can reference these
variables directly in your config.

---

## State Management

CCFM stores deployment state remotely in Confluence itself — no local state files to commit
or sync. Each tracked page is stored as its own content property (`ccfm-page-<hash>`) on the
`CCFM State Management` page, which lives under a `_ccfm` container page in your space.

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

The command is idempotent — running it again is a no-op. It is a **one-time per-space** operation;
you do not need to run it before every apply.

!!! note
    All files inside your `docs_root` directory are managed by CCFM. Removing files or folders
    will result in destroy operations on the next `ccfm apply`.

### Inspecting and managing state

```bash
# List all tracked pages
ccfm state list

# Show full details for a specific entry
ccfm state show docs/my-page.md

# Download the raw state JSON
ccfm state pull

# Remove a specific entry
ccfm state rm docs/old-page.md
```

### Recovery: push a repaired state file

If state becomes corrupted, download it, edit it locally, then push it back:

```bash
ccfm state pull > state-backup.json
# edit state-backup.json
ccfm state push state-backup.json
```

!!! warning
    `state push` overwrites the remote state completely. Use with caution.

### Migrating from attachment-based state (pre-v2.3)

Releases before v2.3 stored state as a single `ccfm-state.json` attachment on the
management page. Atlassian deprecated and then removed Basic-auth API-token access to
the legacy `/wiki/download/attachments/` path
([CHANGE-2735](https://developer.atlassian.com/changelog/#CHANGE-2735)) — so the old
backend can no longer read its own state on tenants where the change has rolled out
(typically surfaces as `401 Unauthorized` on `ccfm plan` / `apply`).

If you're upgrading and `ccfm state pull` returns nothing or errors:

1. **Download the old state** through the Confluence UI: open the `CCFM State Management`
   page in your browser, find `ccfm-state.json` in its attachments list, and click download.
   (Browser cookie auth still works on that path; only API-token auth is blocked.)
2. **Upgrade ccfm-convert** to v2.3 or later.
3. **Push it to the new backend**: `ccfm state push ccfm-state.json` — this writes one
   `ccfm-page-<hash>` content property per tracked page on the management page.
4. **Optional tidy-up**: delete the `ccfm-state.json` attachment from the management page
   in the Confluence UI; nothing reads it any more.

If the UI download path has also been disabled on your tenant by the time you read this,
contact Atlassian support to retrieve the attachment, or rebuild state from scratch by
running `ccfm apply --force` against a clean management page (every tracked page will be
re-deployed and re-tracked, but no Confluence content is lost in the process).

New installations are unaffected — `ccfm init` and the first `apply` use the property
backend natively.

### Plan and apply workflow

Preview what would change without making any modifications:

```bash
ccfm plan
```

Apply changes interactively (prompts for confirmation):

```bash
ccfm apply
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
- `ccfm plan` does **not** acquire locks (it's read-only)
- Lock owner is auto-detected as `user@hostname`

### CI traceability

Pass `--lock-id` to associate the lock with a CI pipeline for easier debugging:

```bash
ccfm apply --auto-approve --lock-id "$CI_PIPELINE_ID"
```

### Recovering from stale locks

If a CI job crashes mid-apply, the lock may be left in place. Force-release it:

```bash
ccfm lock release
```

Check the lock status first:

```bash
ccfm lock status
```

Output shows whether the lock is held, by whom, when it was acquired, and the lock ID.
