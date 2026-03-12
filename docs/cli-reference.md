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
| `dump` | Convert markdown to ADF JSON files for inspection (no API calls) |
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
--domain DOMAIN        Confluence domain (e.g., company.atlassian.net)
--email EMAIL          User email address
--token TOKEN          Atlassian API token (or set CONFLUENCE_TOKEN env var)
--space SPACE          Space key (e.g., DOCS — not the space display name)
```

---

## Plan

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

---

## Apply

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

---

## Dump

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
