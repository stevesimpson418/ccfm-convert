# CCFM Manual Testing Runbook

Step-by-step manual testing procedure for major feature releases.
Run through these phases in order — each phase builds on the previous one.

## Prerequisites

1. Editable install: `pip install -e .`
2. Credentials configured in `.env.smoke` and `ccfm-smoke.yaml`
3. Source credentials: `source .env.smoke`
4. Clean state: `ccfm --config tests/smoke/ccfm-smoke.yaml state list` should show no pages

> If state is not clean, use `state rm` or reset via `state push` with an empty state file.

---

## Phase 1: Verify CLI Help

Verify all subcommands print help and exit 0.

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 1.1 | `ccfm --help` | Shows subcommands: init, plan, apply, state, lock (no dump) | |
| 1.2 | `ccfm init --help` | Shows init options | |
| 1.3 | `ccfm plan --help` | Shows `--debug-file`, `--plan-exit-code`, `--force`, `--git-repo-url`. No `--file`, `--directory`, `--docs-root`, `--auto-deploy-deps` | |
| 1.4 | `ccfm apply --help` | Shows `--auto-approve`, `--force`, `--lock-id`, `--git-repo-url`. No `--file`, `--directory`, `--docs-root`, `--auto-deploy-deps` | |
| 1.5 | `ccfm state --help` | Shows list, pull, push, rm, show | |
| 1.6 | `ccfm lock --help` | Shows status, acquire, release | |

---

## Phase 2: Plan

```bash
CFG="--config tests/smoke/ccfm-smoke.yaml"
```

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 2.1 | `ccfm plan` (from a directory with no `ccfm.yaml`) | Error: "No docs_root configured" | |
| 2.2 | `ccfm $CFG plan` | "Plan: 8 to add." (uses docs_root from config) | |
| 2.4 | `ccfm $CFG plan --plan-exit-code; echo $?` | Exit code 2 (pending changes) | |
| 2.5 | `ccfm $CFG plan --force` | "Plan: 8 to add." (force treats all as new) | |

---

## Phase 3: Apply (initial deployment)

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 3.1 | `ccfm $CFG apply` | Prompts for "yes", deploys all pages on "yes" | |
| 3.2 | `ccfm $CFG apply --auto-approve` | "No changes to apply." (idempotent) | |
| 3.3 | Edit single-page.md, then `ccfm $CFG apply --auto-approve` | "Plan: 1 to change." then updates | |
| 3.4 | Revert edit, then `ccfm $CFG apply --auto-approve` | Updates back (1 to change) | |
| 3.5 | `ccfm $CFG apply --force --auto-approve` | "Plan: 8 to add." (force re-deploys all) | |
| 3.6 | `ccfm $CFG apply --auto-approve` | "No changes to apply." | |
| 3.7 | `ccfm $CFG plan --plan-exit-code; echo $?` | Exit code 0 (no pending changes) | |

### Interactive prompt

| # | Input | Expected | Pass/Fail |
| --- | ------- | ---------- | ----------- |
| 3.8 | `ccfm $CFG apply --force`, type `no` | "Apply cancelled." | |
| 3.9 | `ccfm $CFG apply --force`, type `y` | "Apply cancelled." (only "yes" accepted) | |
| 3.10 | `ccfm $CFG apply --force`, type `Yes` | Proceeds (case-insensitive) | |

---

## Phase 4: Debug File

No credentials needed for these steps.

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 4.1 | `ccfm plan --debug-file tests/smoke/docs/single-page/single-page.md` | Prints valid ADF JSON to stdout | |
| 4.2 | `ccfm plan --debug-file tests/smoke/docs/single-page/single-page.md \| jq .type` | Prints `"doc"` | |
| 4.3 | `ccfm plan --debug-file "tests/smoke/docs/example/CCFM Example/complete_example.md"` | Succeeds (no crash on page links) | |
| 4.4 | `ccfm plan --debug-file tests/smoke/docs/single-page/single-page.md --git-repo-url https://github.com/org/repo` | ADF JSON includes CI banner panel as first content node | |
| 4.5 | Create a temp file with `ci_banner: false` frontmatter, run `--debug-file` against it | ADF JSON has heading as first content node (no banner) | |

---

## Phase 5: Destroy

| # | Step | Expected | Pass/Fail |
| --- | ------ | ---------- | ----------- |
| 5.1 | Temporarily move `single-page.md` out of the docs dir | | |
| 5.2 | `ccfm $CFG plan` | Shows "1 to destroy" for single-page (and container) | |
| 5.3 | `ccfm $CFG apply --auto-approve` | Destroys single-page and its container | |
| 5.4 | `ccfm $CFG apply --auto-approve` | "No changes to apply." | |
| 5.5 | Move `single-page.md` back | | |
| 5.6 | `ccfm $CFG apply --auto-approve` | "Plan: 1 to add." — re-creates page | |

### deploy_page: false destroy

| # | Step | Expected | Pass/Fail |
| --- | ------ | ---------- | ----------- |
| 5.7 | Set `deploy_page: false` in single-page.md frontmatter | | |
| 5.8 | `ccfm $CFG plan` | Shows "to destroy" for single-page (and container) | |
| 5.9 | `ccfm $CFG apply --auto-approve` | Destroys single-page, removes from state | |
| 5.10 | `ccfm $CFG apply --auto-approve` | "No changes to apply." | |
| 5.11 | Revert single-page.md (remove `deploy_page: false`) | | |
| 5.12 | `ccfm $CFG apply --auto-approve` | "Plan: 1 to add." — re-creates page | |

---

## Phase 6: State Commands

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 6.1 | `ccfm $CFG state list` | Shows all 16 tracked pages (8 md + 8 container) | |
| 6.2 | `ccfm $CFG state show "tests/smoke/docs/single-page/single-page.md"` | Shows page_id, content_hash, title | |
| 6.3 | `ccfm $CFG state pull > state-backup.json` | Valid JSON with "pages" and "version" keys | |
| 6.4 | `ccfm $CFG state push state-backup.json` | "Remote state updated" | |
| 6.5 | `ccfm $CFG state rm "tests/smoke/docs/single-page/single-page.md"` | "Removed '...' from state." | |
| 6.6 | `ccfm $CFG state list` | Entry no longer present | |
| 6.7 | `ccfm $CFG state push state-backup.json` | Restore original state | |

---

## Phase 7: Lock

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 7.1 | `ccfm $CFG lock status` | "State is not locked." | |
| 7.2 | `ccfm $CFG lock acquire` | "Lock acquired by ..." | |
| 7.3 | `ccfm $CFG lock status` | Shows lock owner, timestamp, operation | |
| 7.4 | `ccfm $CFG apply --auto-approve --force` | Error: "State is locked by ..." | |
| 7.5 | `ccfm $CFG lock release` | "Lock released." | |
| 7.6 | `ccfm $CFG lock status` | "State is not locked." | |
| 7.7 | `ccfm $CFG lock release` | Succeeds (idempotent) | |

---

## Phase 8: Error Handling

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 8.1 | `ccfm plan` (from dir with no `ccfm.yaml`) | "Error: No docs_root configured" | |
| 8.2 | `ccfm plan --debug-file nonexistent.md` | "error: File not found: nonexistent.md" | |
| 8.3 | `ccfm apply` (from dir with no `ccfm.yaml`) | "Error: No docs_root configured" | |

---

## Phase 9: Dependency Ordering

The example directory has page links: `complete_example.md` links to `My Team` and `My App`.

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 9.1 | `ccfm $CFG plan` | Plan output has no cycle or unresolved link warnings | |
| 9.2 | `ccfm $CFG apply --auto-approve --force` | Pages deploy without "Page not found for link" warnings (deps deployed first) | |
| 9.3 | Verify in Confluence: `complete_example` page has working smart links to My Team and My App | Links resolve correctly | |

---

## Cleanup

After testing, remove test pages from Confluence and reset state:

```bash
# Option A: Use the smoke test cleanup
pytest tests/smoke/ --no-cov -v --cleanup-only

# Option B: Manual reset
ccfm $CFG state push /dev/stdin <<< '{"version": "1", "pages": {}}'
# Then manually delete pages from Confluence UI
```
