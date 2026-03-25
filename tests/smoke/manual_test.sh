#!/usr/bin/env bash
# Interactive manual testing script for CCFM CLI.
# Walks through all phases from MANUAL_TESTING.md step by step.
#
# Usage:
#   source .env.smoke
#   ./tests/smoke/manual_test.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

CFG="--config tests/smoke/ccfm-smoke.yaml"
SINGLE_PAGE="tests/smoke/docs/single-page/single-page.md"
COMPLETE_EXAMPLE="tests/smoke/docs/example/CCFM Example/complete_example.md"
SMOKE_DOCS="tests/smoke/docs"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No colour

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

phase() {
    echo ""
    echo -e "${YELLOW}================================================================${NC}"
    echo -e "${YELLOW}  $1${NC}"
    echo -e "${YELLOW}================================================================${NC}"
    echo ""
}

step_header() {
    local num="$1"
    local desc="$2"
    local expected="$3"
    echo -e "${CYAN}--- Step $num ---${NC}"
    echo -e "${BOLD}$desc${NC}"
    echo -e "${DIM}Expected: $expected${NC}"
    echo ""
}

run_cmd() {
    # Run a command, show it, then show output.
    local cmd="$*"
    echo -e "${DIM}\$ $cmd${NC}"
    echo ""
    eval "$cmd" 2>&1 || true
    echo ""
}

run_cmd_interactive() {
    # Run a command that needs direct TTY access (interactive prompts).
    local cmd="$*"
    echo -e "${DIM}\$ $cmd${NC}"
    echo ""
    eval "$cmd" || true
    echo ""
}

verdict() {
    # Ask user for pass/fail verdict.
    echo -e -n "${BOLD}Result? [${GREEN}P${NC}${BOLD}ass / ${RED}F${NC}${BOLD}ail / ${YELLOW}S${NC}${BOLD}kip / ${RED}Q${NC}${BOLD}uit]: ${NC}"
    read -r v
    local lv
    lv="$(echo "$v" | tr '[:upper:]' '[:lower:]')"
    case "$lv" in
        f|fail)
            echo -e "${RED}FAIL${NC}"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            ;;
        s|skip)
            echo -e "${YELLOW}SKIP${NC}"
            SKIP_COUNT=$((SKIP_COUNT + 1))
            ;;
        q|quit)
            echo ""
            summary
            exit 0
            ;;
        *)
            echo -e "${GREEN}PASS${NC}"
            PASS_COUNT=$((PASS_COUNT + 1))
            ;;
    esac
    echo ""
}

manual_note() {
    echo -e "${YELLOW}>> $1${NC}"
}

summary() {
    echo ""
    echo -e "${BOLD}================================================================${NC}"
    echo -e "${BOLD}  RESULTS${NC}"
    echo -e "${BOLD}================================================================${NC}"
    echo -e "  ${GREEN}Passed: $PASS_COUNT${NC}"
    echo -e "  ${RED}Failed: $FAIL_COUNT${NC}"
    echo -e "  ${YELLOW}Skipped: $SKIP_COUNT${NC}"
    total=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))
    echo -e "  Total:  $total"
    echo ""
    if [ "$FAIL_COUNT" -eq 0 ]; then
        echo -e "  ${GREEN}All tests passed!${NC}"
    else
        echo -e "  ${RED}$FAIL_COUNT test(s) failed.${NC}"
    fi
    echo ""
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

if [ -z "${CONFLUENCE_DOMAIN:-}" ] || [ -z "${CONFLUENCE_TOKEN:-}" ]; then
    echo -e "${RED}Error: Credentials not set. Run: source .env.smoke${NC}"
    exit 1
fi

echo -e "${BOLD}CCFM Interactive Manual Test Runner${NC}"
echo -e "${DIM}Project root: $PROJECT_ROOT${NC}"
echo -e "${DIM}Config: tests/smoke/ccfm-smoke.yaml${NC}"
echo ""
echo "Press Enter to start, or Ctrl-C to abort."
read -r

# ===================================================================
# Phase 1: CLI Help
# ===================================================================

phase "Phase 1: Verify CLI Help"

step_header "1.1" "Root help" "Shows subcommands: init, plan, apply, state, lock (no dump)"
run_cmd ccfm --help
verdict

step_header "1.2" "Init help" "Shows init options"
run_cmd ccfm init --help
verdict

step_header "1.3" "Plan help" "Shows --docs-root, --debug-file, --plan-exit-code, --force. No --file/--directory"
run_cmd ccfm plan --help
verdict

step_header "1.4" "Apply help" "Shows --docs-root, --auto-approve, --force, --lock-id. No --file/--directory"
run_cmd ccfm apply --help
verdict

step_header "1.5" "State help" "Shows list, pull, push, rm, show"
run_cmd ccfm state --help
verdict

step_header "1.6" "Lock help" "Shows status, acquire, release"
run_cmd ccfm lock --help
verdict

# ===================================================================
# Phase 2: Plan
# ===================================================================

phase "Phase 2: Plan"

step_header "2.1" "Plan with no docs_root" "Error: No docs_root configured"
# Run from /tmp to ensure no ccfm.yaml is found
run_cmd "cd /tmp && ccfm plan; cd '$PROJECT_ROOT'"
verdict

step_header "2.2" "Plan docs_root from config" "Plan: 8 to add."
run_cmd ccfm $CFG plan
verdict

step_header "2.3" "Plan with --docs-root override" "Plan: 1 to add. (overrides config docs_root)"
run_cmd ccfm $CFG plan --docs-root "$SMOKE_DOCS/single-page"
verdict

step_header "2.4" "Plan with --plan-exit-code (pending changes)" "Exit code 2"
echo -e "${DIM}\$ ccfm $CFG plan --plan-exit-code${NC}"
echo ""
rc=0
ccfm $CFG plan --plan-exit-code || rc=$?
echo ""
echo -e "${DIM}Exit code: $rc${NC}"
verdict

step_header "2.5" "Plan with --force" "Plan: 8 to add. (force treats all as new)"
run_cmd ccfm $CFG plan --force
verdict

# ===================================================================
# Phase 3: Apply (initial deployment)
# ===================================================================

phase "Phase 3: Apply (initial deployment)"

step_header "3.1" "Apply (interactive)" "Prompts for 'yes', deploys all pages on 'yes'"
manual_note "Type 'yes' at the prompt"
run_cmd_interactive ccfm $CFG apply
verdict

step_header "3.2" "Re-apply (idempotent)" "No changes to apply."
run_cmd ccfm $CFG apply --auto-approve
verdict

step_header "3.3" "Apply changed file" "Plan: 1 to change. then updates"
manual_note "Appending a line to single-page.md for change detection..."
echo "" >> "$SINGLE_PAGE"
echo "<!-- manual test change -->" >> "$SINGLE_PAGE"
run_cmd ccfm $CFG apply --auto-approve
manual_note "Reverting change..."
git checkout -- "$SINGLE_PAGE"
verdict

step_header "3.4" "Apply reverted change" "Plan: 1 to change. (reverts back)"
run_cmd ccfm $CFG apply --auto-approve
verdict

step_header "3.5" "Apply with --force --auto-approve" "Plan: 8 to add. (force re-deploys all)"
run_cmd ccfm $CFG apply --force --auto-approve
verdict

step_header "3.6" "Re-apply (no changes)" "No changes to apply."
run_cmd ccfm $CFG apply --auto-approve
verdict

step_header "3.7" "Plan --plan-exit-code after full deploy" "Exit code 0 (no pending changes)"
echo -e "${DIM}\$ ccfm $CFG plan --plan-exit-code${NC}"
echo ""
rc=0
ccfm $CFG plan --plan-exit-code || rc=$?
echo ""
echo -e "${DIM}Exit code: $rc${NC}"
verdict

step_header "3.8" "Interactive rejection: 'no'" "Apply cancelled."
manual_note "Type 'no' at the prompt"
run_cmd_interactive ccfm $CFG apply --force
verdict

step_header "3.9" "Interactive rejection: 'y'" "Apply cancelled. (only 'yes' accepted)"
manual_note "Type 'y' at the prompt"
run_cmd_interactive ccfm $CFG apply --force
verdict

step_header "3.10" "Interactive accept: 'Yes'" "Proceeds (case-insensitive)"
manual_note "Type 'Yes' at the prompt"
run_cmd_interactive ccfm $CFG apply --force
verdict

# ===================================================================
# Phase 4: Debug File
# ===================================================================

phase "Phase 4: Debug File (no credentials needed)"

step_header "4.1" "Debug file single page" "Prints ADF JSON to stdout"
run_cmd ccfm plan --debug-file "$SINGLE_PAGE"
verdict

step_header "4.2" "Debug file piped to jq" 'Prints "doc"'
run_cmd ccfm plan --debug-file "$SINGLE_PAGE" '|' jq .type
verdict

step_header "4.3" "Debug file with page links (regression)" "Succeeds (no crash on page links)"
run_cmd ccfm plan --debug-file "$COMPLETE_EXAMPLE"
verdict

step_header "4.4" "Debug file with --git-repo-url" "ADF JSON has panel (CI banner) as first content node"
run_cmd ccfm plan --debug-file "$SINGLE_PAGE" --git-repo-url "https://github.com/org/repo" '|' jq '.content[0].type'
verdict

step_header "4.5" "Debug file with ci_banner: false" "ADF JSON has heading as first node (no banner)"
TMPFILE=$(mktemp /tmp/ccfm-test-XXXXX.md)
echo -e "---\ndeploy_config:\n  ci_banner: false\n---\n# No Banner" > "$TMPFILE"
run_cmd ccfm plan --debug-file "$TMPFILE" '|' jq '.content[0].type'
rm -f "$TMPFILE"
verdict

# ===================================================================
# Phase 5: Destroy
# ===================================================================

phase "Phase 5: Destroy"

step_header "5.1-5.2" "Move file and plan destroy" "Shows destroy for single-page and its container"
mv "$SINGLE_PAGE" "$SINGLE_PAGE.bak"
run_cmd ccfm $CFG plan
verdict

step_header "5.3" "Apply destroy" "Destroys single-page and its container"
run_cmd ccfm $CFG apply --auto-approve
verdict

step_header "5.4" "Re-apply after destroy (no changes)" "No changes to apply."
run_cmd ccfm $CFG apply --auto-approve
verdict

step_header "5.5-5.6" "Restore file and re-add" "Plan: 1 to add. Re-creates page"
mv "$SINGLE_PAGE.bak" "$SINGLE_PAGE"
run_cmd ccfm $CFG apply --auto-approve
verdict

# --- deploy_page: false destroy ---

step_header "5.7-5.8" "Set deploy_page: false and plan" "Shows destroy for single-page"
manual_note "Injecting deploy_page: false into single-page.md frontmatter..."
cp "$SINGLE_PAGE" "$SINGLE_PAGE.bak"
python3 -c "
p = '$SINGLE_PAGE'
txt = open(p).read()
if txt.startswith('---'):
    parts = txt.split('---', 2)
    parts[1] = parts[1].rstrip() + '\ndeploy_config:\n  deploy_page: false\n'
    open(p, 'w').write('---'.join(parts))
else:
    open(p, 'w').write('---\ndeploy_config:\n  deploy_page: false\n---\n' + txt)
"
run_cmd ccfm $CFG plan
verdict

step_header "5.9" "Apply deploy_page: false destroy" "Destroys single-page, removes from state"
run_cmd ccfm $CFG apply --auto-approve
verdict

step_header "5.10" "Re-apply after deploy_page: false destroy" "No changes to apply."
run_cmd ccfm $CFG apply --auto-approve
verdict

step_header "5.11-5.12" "Revert deploy_page: false and re-add" "Plan: 1 to add. Re-creates page"
manual_note "Reverting single-page.md..."
mv "$SINGLE_PAGE.bak" "$SINGLE_PAGE"
run_cmd ccfm $CFG apply --auto-approve
verdict

# ===================================================================
# Phase 6: State Commands
# ===================================================================

phase "Phase 6: State Commands"

step_header "6.1" "State list" "Shows tracked pages (8 md + 8 container = 16)"
run_cmd ccfm $CFG state list
verdict

step_header "6.2" "State show" "Shows page_id, content_hash, title"
run_cmd ccfm $CFG state show "$SINGLE_PAGE"
verdict

step_header "6.3" "State pull" "Valid JSON with pages and version keys"
run_cmd ccfm $CFG state pull
# Save for later use
ccfm $CFG state pull > /tmp/ccfm-state-backup.json 2>/dev/null
verdict

step_header "6.4" "State push (round-trip)" "Remote state updated"
run_cmd ccfm $CFG state push /tmp/ccfm-state-backup.json
verdict

step_header "6.5" "State rm" "Removed from state"
run_cmd ccfm $CFG state rm "$SINGLE_PAGE"
verdict

step_header "6.6" "State list (verify removal)" "Entry no longer present"
run_cmd ccfm $CFG state list
verdict

step_header "6.7" "State push (restore)" "Restore original state"
run_cmd ccfm $CFG state push /tmp/ccfm-state-backup.json
rm -f /tmp/ccfm-state-backup.json
verdict

# ===================================================================
# Phase 7: Lock
# ===================================================================

phase "Phase 7: Lock"

step_header "7.1" "Lock status (unlocked)" "State is not locked."
run_cmd ccfm $CFG lock status
verdict

step_header "7.2" "Lock acquire" "Lock acquired by ..."
run_cmd ccfm $CFG lock acquire
verdict

step_header "7.3" "Lock status (locked)" "Shows lock owner, timestamp, operation"
run_cmd ccfm $CFG lock status
verdict

step_header "7.4" "Apply blocked by lock" "Error: State is locked by ..."
run_cmd ccfm $CFG apply --auto-approve --force
verdict

step_header "7.5" "Lock release" "Lock released."
run_cmd ccfm $CFG lock release
verdict

step_header "7.6" "Lock status (unlocked again)" "State is not locked."
run_cmd ccfm $CFG lock status
verdict

step_header "7.7" "Lock release (idempotent)" "Succeeds"
run_cmd ccfm $CFG lock release
verdict

# ===================================================================
# Phase 8: Error Handling
# ===================================================================

phase "Phase 8: Error Handling"

step_header "8.1" "No docs_root configured" "Error: No docs_root configured"
run_cmd "cd /tmp && ccfm plan; cd '$PROJECT_ROOT'"
verdict

step_header "8.2" "Missing docs_root directory" "Error: docs_root not found: nonexistent-dir"
run_cmd ccfm plan --docs-root nonexistent-dir
verdict

step_header "8.3" "docs_root is a file, not a directory" "Error: docs_root is not a directory"
run_cmd ccfm plan --docs-root "$SINGLE_PAGE"
verdict

step_header "8.4" "Debug file missing" "error: File not found: nonexistent.md"
run_cmd ccfm plan --debug-file nonexistent.md
verdict

step_header "8.5" "Apply with no docs_root" "Error: No docs_root configured"
run_cmd "cd /tmp && ccfm apply --auto-approve; cd '$PROJECT_ROOT'"
verdict

# ===================================================================
# Phase 9: Dependency Ordering
# ===================================================================

phase "Phase 9: Dependency Ordering"

step_header "9.1" "Plan shows dependency order" "Output includes 'Deploy order:' line"
run_cmd ccfm $CFG plan
verdict

step_header "9.2" "Force apply deploys in dependency order" "No 'Page not found for link' warnings"
run_cmd ccfm $CFG apply --auto-approve --force
verdict

step_header "9.3" "Verify page links in Confluence" "complete_example has working smart links to My Team and My App"
manual_note "Open complete_example page in Confluence and verify smart links work."
verdict

# ===================================================================
# Summary
# ===================================================================

summary
