# CCFM Manual Testing Runbook

Step-by-step manual testing procedure for major feature releases.
Run through these phases in order — each phase builds on the previous one.

## Prerequisites

1. Editable install: `pip install -e .`
2. Credentials configured in `.env.smoke` or `ccfm-smoke.yaml`
3. Source credentials: `source .env.smoke`
4. Clean state: `ccfm --config tests/smoke/ccfm-smoke.yaml state list` should show no pages

> If state is not clean, use `state rm` or reset via `state push` with an empty state file.

---

## Phase 1: Verify CLI Help

Verify all subcommands print help and exit 0.

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 1.1 | `ccfm --help` | Shows all subcommands (init, plan, apply, dump, state, lock) | |
| 1.2 | `ccfm init --help` | Shows init options | |
| 1.3 | `ccfm plan --help` | Shows `--file`, `--directory`, `--plan-exit-code`, `--force`, `--auto-deploy-deps` | |
| 1.4 | `ccfm apply --help` | Shows `--auto-approve`, `--force`, `--lock-id`, `--auto-deploy-deps` | |
| 1.5 | `ccfm dump --help` | Shows `--file`, `--directory`, `--output-dir` | |
| 1.6 | `ccfm state --help` | Shows list, pull, push, rm, show | |
| 1.7 | `ccfm lock --help` | Shows status, acquire, release | |

---

## Phase 2: Plan

```bash
CFG="--config tests/smoke/ccfm-smoke.yaml"
```

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 2.1 | `ccfm $CFG plan` | Error: "Specify either --file or --directory" | |
| 2.2 | `ccfm $CFG plan --file tests/smoke/docs/single-page/single-page.md` | "Plan: 1 to add." | |
| 2.3 | `ccfm $CFG plan --directory tests/smoke/docs` | "Plan: 8 to add." | |
| 2.4 | `ccfm $CFG plan --directory tests/smoke/docs --plan-exit-code; echo $?` | Exit code 2 | |

---

## Phase 3: Apply

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 3.1 | `ccfm $CFG apply --file tests/smoke/docs/single-page/single-page.md` | Prompts for "yes", creates page on "yes" | |
| 3.2 | Repeat 3.1 | "No changes. Your Confluence pages are up to date." | |
| 3.3 | Edit single-page.md, repeat 3.1 | "Plan: 1 to change." then updates page | |
| 3.4 | Revert edit, then: `ccfm $CFG apply --directory tests/smoke/docs --auto-approve` | Deploys all 8 files, no prompt | |
| 3.5 | Repeat 3.4 | "No changes to apply." | |
| 3.6 | `ccfm $CFG apply --directory tests/smoke/docs --force` | "Plan: 8 to add." (force treats all as new) | |
| 3.7 | `ccfm $CFG apply --directory tests/smoke/docs --force --auto-approve` | Same as 3.6, no prompt | |

### Interactive prompt rejection

| # | Input | Expected | Pass/Fail |
| --- | ------- | ---------- | ----------- |
| 3.8 | Type `no` at prompt | "Apply cancelled." | |
| 3.9 | Type `y` at prompt | "Apply cancelled." (only "yes" accepted) | |
| 3.10 | Type `Yes` at prompt | Proceeds (case-insensitive) | |

---

## Phase 4: Dump

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 4.1 | `ccfm dump --file tests/smoke/docs/single-page/single-page.md` | Creates `.ccfm/dumps/<timestamp>/` dir with .adf.json | |
| 4.2 | `ccfm dump --directory tests/smoke/docs --output-dir /tmp/adf-test` | Writes 8 .adf.json files to `/tmp/adf-test` | |
| 4.3 | `ccfm dump --file tests/smoke/docs/example/CCFM\ Example/complete_example.md` | Succeeds (no NoneType crash on page links) | |

> Clean up: `rm -rf .ccfm/dumps /tmp/adf-test`

---

## Phase 5: Destroy

| # | Step | Expected | Pass/Fail |
| --- | ------ | ---------- | ----------- |
| 5.1 | Temporarily move `single-page.md` out of the docs dir | | |
| 5.2 | `ccfm $CFG plan --directory tests/smoke/docs` | Shows "1 to destroy" for single-page | |
| 5.3 | `ccfm $CFG apply --directory tests/smoke/docs --auto-approve` | Destroys single-page and its container | |
| 5.4 | Repeat 5.3 | "No changes to apply." | |
| 5.5 | Move `single-page.md` back | | |
| 5.6 | `ccfm $CFG apply --directory tests/smoke/docs --auto-approve` | "Plan: 1 to add." — re-creates page | |

### deploy_page: false destroy

| # | Step | Expected | Pass/Fail |
| --- | ------ | ---------- | ----------- |
| 5.7 | Set `deploy_page: false` in single-page.md frontmatter | | |
| 5.8 | `ccfm $CFG plan --directory tests/smoke/docs` | Shows "to destroy" for single-page (and its container) | |
| 5.9 | `ccfm $CFG apply --directory tests/smoke/docs --auto-approve` | Destroys single-page, removes from state | |
| 5.10 | Repeat 5.9 | "No changes to apply." | |
| 5.11 | Revert single-page.md (remove `deploy_page: false`) | | |
| 5.12 | `ccfm $CFG apply --directory tests/smoke/docs --auto-approve` | "Plan: 1 to add." — re-creates page | |

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
| 7.4 | `ccfm $CFG apply --directory tests/smoke/docs --auto-approve --force` | Error: "State is locked by ..." | |
| 7.5 | `ccfm $CFG lock release` | "Lock released." | |
| 7.6 | `ccfm $CFG lock status` | "State is not locked." | |
| 7.7 | `ccfm $CFG lock release` | Succeeds (idempotent) | |

---

## Phase 8: Error Handling

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 8.1 | `ccfm $CFG apply --file nonexistent.md` | "Error: File not found: nonexistent.md" | |
| 8.2 | `ccfm $CFG apply --directory nonexistent-dir` | "Error: Directory not found: nonexistent-dir" | |
| 8.3 | `ccfm $CFG apply` | "Error: Specify either --file or --directory" | |

---

## Phase 9: Dependency Ordering

Verify that directory deploys use dependency ordering and `--auto-deploy-deps` works.

| # | Command | Expected | Pass/Fail |
| --- | --------- | ---------- | ----------- |
| 9.1 | `ccfm $CFG plan --directory tests/smoke/docs/example` | Plan shows deploy order (Page B, Page C before pages that link to them) | |
| 9.2 | `ccfm $CFG apply --directory tests/smoke/docs/example --auto-approve` | Pages deploy without "Page not found for link" warnings (dependencies deployed first) | |
| 9.3 | `ccfm $CFG apply --file "tests/smoke/docs/example/CCFM Example/complete_example.md" --auto-deploy-deps --docs-root tests/smoke/docs/example --auto-approve --force` | Deploys complete_example.md AND its dependencies (My Team, My App); no broken link warnings | |
| 9.4 | `ccfm $CFG plan --file "tests/smoke/docs/example/CCFM Example/complete_example.md" --auto-deploy-deps --docs-root tests/smoke/docs/example` | Plan shows all dependency files, not just the target | |
| 9.5 | `ccfm $CFG apply --file "tests/smoke/docs/example/CCFM Example/complete_example.md"` | Deploys only complete_example.md (no --auto-deploy-deps); warnings for missing links are expected | |

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
