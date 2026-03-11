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

step_header "1.1" "Root help" "Shows all subcommands (init, plan, apply, dump, state, lock)"
run_cmd ccfm --help
verdict

step_header "1.2" "Init help" "Shows init options"
run_cmd ccfm init --help
verdict

step_header "1.3" "Plan help" "Shows --file, --directory, --plan-exit-code, --force"
run_cmd ccfm plan --help
verdict

step_header "1.4" "Apply help" "Shows --auto-approve, --force, --lock-id"
run_cmd ccfm apply --help
verdict

step_header "1.5" "Dump help" "Shows --file, --directory, --output-dir"
run_cmd ccfm dump --help
verdict

step_header "1.6" "State help" "Shows list, pull, push, rm, show"
run_cmd ccfm state --help
verdict

step_header "1.7" "Lock help" "Shows status, acquire, release"
run_cmd ccfm lock --help
verdict

# ===================================================================
# Phase 2: Plan
# ===================================================================

phase "Phase 2: Plan"

step_header "2.1" "Plan with no target" "Error: Specify either --file or --directory"
run_cmd ccfm $CFG plan
verdict

step_header "2.2" "Plan single file" "Plan: 1 to add."
run_cmd ccfm $CFG plan --file "$SINGLE_PAGE"
verdict

step_header "2.3" "Plan directory" "Plan: 7 to add."
run_cmd ccfm $CFG plan --directory "$SMOKE_DOCS"
verdict

step_header "2.4" "Plan with --plan-exit-code" "Exit code 2"
echo -e "${DIM}\$ ccfm $CFG plan --directory $SMOKE_DOCS --plan-exit-code${NC}"
echo ""
rc=0
ccfm $CFG plan --directory "$SMOKE_DOCS" --plan-exit-code || rc=$?
echo ""
echo -e "${DIM}Exit code: $rc${NC}"
verdict

# ===================================================================
# Phase 3: Apply
# ===================================================================

phase "Phase 3: Apply"

step_header "3.1" "Apply single file (interactive)" "Prompts for 'yes', creates page on 'yes'"
manual_note "Type 'yes' at the prompt"
run_cmd_interactive ccfm $CFG apply --file "$SINGLE_PAGE"
verdict

step_header "3.2" "Re-apply unchanged file" "No changes. Your Confluence pages are up to date."
run_cmd ccfm $CFG apply --auto-approve --file "$SINGLE_PAGE"
verdict

step_header "3.3" "Apply changed file (interactive)" "Plan: 1 to change."
manual_note "Appending a line to single-page.md for change detection..."
echo "" >> "$SINGLE_PAGE"
echo "<!-- manual test change -->" >> "$SINGLE_PAGE"
manual_note "Type 'yes' at the prompt"
run_cmd_interactive ccfm $CFG apply --file "$SINGLE_PAGE"
manual_note "Reverting change..."
git checkout -- "$SINGLE_PAGE"
verdict

step_header "3.4" "Apply directory with --auto-approve" "Deploys all 7 files, no prompt"
run_cmd ccfm $CFG apply --directory "$SMOKE_DOCS" --auto-approve
verdict

step_header "3.5" "Re-apply directory (no changes)" "No changes to apply."
run_cmd ccfm $CFG apply --directory "$SMOKE_DOCS" --auto-approve
verdict

step_header "3.6" "Apply with --force (interactive)" "Plan: 7 to add. (force treats all as new)"
manual_note "Type 'yes' at the prompt"
run_cmd_interactive ccfm $CFG apply --directory "$SMOKE_DOCS" --force
verdict

step_header "3.7" "Apply with --force --auto-approve" "Same as 3.6, no prompt"
run_cmd ccfm $CFG apply --directory "$SMOKE_DOCS" --force --auto-approve
verdict

step_header "3.8" "Interactive rejection: 'no'" "Apply cancelled."
manual_note "Type 'no' at the prompt"
run_cmd_interactive ccfm $CFG apply --directory "$SMOKE_DOCS" --force
verdict

step_header "3.9" "Interactive rejection: 'y'" "Apply cancelled. (only 'yes' accepted)"
manual_note "Type 'y' at the prompt"
run_cmd_interactive ccfm $CFG apply --directory "$SMOKE_DOCS" --force
verdict

step_header "3.10" "Interactive accept: 'Yes'" "Proceeds (case-insensitive)"
manual_note "Type 'Yes' at the prompt"
run_cmd_interactive ccfm $CFG apply --directory "$SMOKE_DOCS" --force
verdict

# ===================================================================
# Phase 4: Dump
# ===================================================================

phase "Phase 4: Dump"

step_header "4.1" "Dump single file" "Creates .ccfm/dumps/<timestamp>/ dir with .adf.json"
run_cmd ccfm dump --file "$SINGLE_PAGE"
echo -e "${DIM}Dump directories:${NC}"
ls .ccfm/dumps/ 2>/dev/null || echo "(none found)"
verdict

step_header "4.2" "Dump directory with --output-dir" "Writes .adf.json files to /tmp/ccfm-manual-test"
rm -rf /tmp/ccfm-manual-test
run_cmd ccfm dump --directory "$SMOKE_DOCS" --output-dir /tmp/ccfm-manual-test
echo -e "${DIM}Output files:${NC}"
find /tmp/ccfm-manual-test -name "*.adf.json" 2>/dev/null | head -20
verdict

step_header "4.3" "Dump file with page links (regression)" "Succeeds (no NoneType crash)"
run_cmd ccfm dump --file "\"$COMPLETE_EXAMPLE\"" --output-dir /tmp/ccfm-manual-test-links
verdict

# Cleanup dump output
rm -rf .ccfm/dumps /tmp/ccfm-manual-test /tmp/ccfm-manual-test-links

# ===================================================================
# Phase 5: Destroy
# ===================================================================

phase "Phase 5: Destroy"

step_header "5.1-5.2" "Move file and plan destroy" "Shows destroy for single-page"
mv "$SINGLE_PAGE" "$SINGLE_PAGE.bak"
run_cmd ccfm $CFG plan --directory "$SMOKE_DOCS"
verdict

step_header "5.3" "Apply destroy" "Destroys single-page and its container"
run_cmd ccfm $CFG apply --directory "$SMOKE_DOCS" --auto-approve
verdict

step_header "5.4" "Re-apply after destroy (no changes)" "No changes to apply."
run_cmd ccfm $CFG apply --directory "$SMOKE_DOCS" --auto-approve
verdict

step_header "5.5-5.6" "Restore file and re-add" "Plan: 1 to add. Re-creates page"
mv "$SINGLE_PAGE.bak" "$SINGLE_PAGE"
run_cmd ccfm $CFG apply --directory "$SMOKE_DOCS" --auto-approve
verdict

# ===================================================================
# Phase 6: State Commands
# ===================================================================

phase "Phase 6: State Commands"

step_header "6.1" "State list" "Shows tracked pages"
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
run_cmd ccfm $CFG apply --directory "$SMOKE_DOCS" --auto-approve --force
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

step_header "8.1" "Apply missing file" "Error: File not found: nonexistent.md"
run_cmd ccfm $CFG apply --file nonexistent.md
verdict

step_header "8.2" "Apply missing directory" "Error: Directory not found: nonexistent-dir"
run_cmd ccfm $CFG apply --directory nonexistent-dir
verdict

step_header "8.3" "Apply no target" "Error: Specify either --file or --directory"
run_cmd ccfm $CFG apply
verdict

# ===================================================================
# Summary
# ===================================================================

summary
