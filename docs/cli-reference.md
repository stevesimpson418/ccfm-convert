# CLI Reference

CCFM uses subcommands. Global credential options must come **before** the subcommand:

```text
ccfm [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]
```

## Commands

| Command | Description |
| --- | --- |
| `init` | Initialise remote state in a Confluence space |
| `plan` | Preview what would change without making modifications |
| `apply` | Apply changes to Confluence (add, change, destroy) |
| `state list` | List all pages tracked in remote state |
| `state pull` | Print remote state JSON to stdout |
| `state push <file>` | Overwrite remote state from a local file |
| `state rm <path>` | Remove a page entry from remote state |
| `state show <path>` | Show state entry for a specific path |
| `lock acquire` | Manually acquire the remote lock |
| `lock status` | Show current lock status |
| `lock release` | Force-release a stale lock |

---

## Global Options

These apply to all commands:

```text
--config PATH          Path to ccfm.yaml config file (default: ccfm.yaml if present)
--domain DOMAIN        Confluence domain (or set CONFLUENCE_DOMAIN env var)
--email EMAIL          User email (or set CONFLUENCE_EMAIL env var)
--token TOKEN          Atlassian API token (or set CONFLUENCE_TOKEN env var)
--space SPACE          Space key (e.g., DOCS — not the space display name)
```

---

## Plan

```text
ccfm plan [OPTIONS]

Options:
  --docs-root PATH       Documentation root directory (or set docs_root in ccfm.yaml)
  --git-repo-url URL     Git repo URL for CI banner source links
  --plan-exit-code       Exit 2 when plan detects pending changes (for CI gates)
  --force                Force re-deploy all files regardless of content changes
  --debug-file PATH      Convert a single file to ADF JSON and print to stdout (no API calls)
```

### docs_root (required)

All deployments target the full `docs_root` directory. The docs_root must be explicitly configured via:

1. `--docs-root` CLI flag (takes precedence), or
2. `docs_root` in `ccfm.yaml`

There is no default — if neither is set, ccfm exits with an error. This prevents accidental deployment of the wrong directory.

The same resolution applies to both `plan` and `apply`.

### Dependency ordering

When deploying, CCFM automatically analyses internal page links and deploys
pages in dependency order (linked pages first). This is handled automatically
for the full docs_root — no extra flags needed.

### Debug file (`--debug-file`)

Use `--debug-file` to convert a single markdown file to ADF JSON and print it to
stdout for inspection. No credentials or API calls are needed:

```bash
ccfm plan --debug-file docs/my-page.md
ccfm plan --debug-file docs/my-page.md --git-repo-url "https://github.com/org/repo"
```

Output can be piped to `jq` or redirected to a file:

```bash
ccfm plan --debug-file docs/my-page.md | jq '.content[0]'
ccfm plan --debug-file docs/my-page.md > my-page.adf.json
```

---

## Apply

```text
ccfm apply [OPTIONS]

Options:
  --docs-root PATH       Documentation root directory (or set docs_root in ccfm.yaml)
  --git-repo-url URL     Git repo URL for CI banner source links
  --auto-approve         Skip confirmation prompt (required for CI/non-interactive use)
  --force                Force re-deploy all files regardless of content changes
  --lock-id ID           Lock identifier for CI traceability (e.g., pipeline ID)
```

---

## State Subcommands

### state list

List all tracked pages:

```bash
ccfm --domain ... --email ... --token ... --space DOCS state list
```

### state show

Show full details for a specific entry:

```bash
ccfm --domain ... --email ... --token ... --space DOCS state show docs/my-page.md
```

### state pull

Download the raw state JSON (useful for piping to `jq` or saving a backup):

```bash
ccfm --domain ... --email ... --token ... --space DOCS state pull
```

### state push

Overwrite remote state from a local file:

```bash
ccfm --domain ... --email ... --token ... --space DOCS state push state-backup.json
```

!!! warning
    `state push` overwrites the remote state completely. Use with caution.

### state rm

Remove a specific entry (e.g., after manually deleting a page in Confluence):

```bash
ccfm --domain ... --email ... --token ... --space DOCS state rm docs/old-page.md
```

---

## Lock Subcommands

### lock status

Check whether the lock is held, by whom, when it was acquired, and the lock ID:

```bash
ccfm --domain ... --email ... --token ... --space DOCS lock status
```

### lock acquire

For maintenance or scripted workflows, acquire the lock without deploying:

```bash
ccfm --domain ... --email ... --token ... --space DOCS lock acquire

# With a custom operation label and lock ID
ccfm --domain ... --email ... --token ... --space DOCS \
  lock acquire --operation maintenance --lock-id "manual-$(date +%s)"
```

### lock release

Force-release a stale lock (e.g., after a crashed CI job):

```bash
ccfm --domain ... --email ... --token ... --space DOCS lock release
```

---

## Examples

```bash
# Initialise CCFM in your space (one-time setup)
ccfm --domain company.atlassian.net --email user@example.com --token abc123 --space DOCS init

# Preview what would change (credentials from ccfm.yaml)
ccfm plan

# Preview with explicit docs_root
ccfm plan --docs-root path/to/docs

# Apply all docs with auto-approve (for CI)
ccfm apply --auto-approve

# Apply with explicit docs_root and CI banner links
ccfm apply --docs-root path/to/docs \
  --git-repo-url "https://github.com/org/repo/blob/main" --auto-approve

# Force re-deploy all files
ccfm apply --force --auto-approve

# Inspect a single file's ADF output
ccfm plan --debug-file docs/team/overview.md

# Check lock status
ccfm --domain company.atlassian.net --email user@example.com --token abc123 --space DOCS \
  lock status

# View tracked pages
ccfm --domain company.atlassian.net --email user@example.com --token abc123 --space DOCS \
  state list
```
