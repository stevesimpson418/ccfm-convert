"""Tests for plan.planner — DeployPlan, PageAction, OrphanAction, compute_plan."""

import os
from pathlib import Path

from plan.planner import DeployPlan, OrphanAction, PageAction, compute_plan
from state.manager import StateManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(tmp_path) -> StateManager:
    return StateManager(tmp_path / ".ccfm-state.json")


def _write_md(directory: Path, name: str, content: str = "# Hello") -> Path:
    f = directory / name
    f.write_text(content, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# DeployPlan.has_changes
# ---------------------------------------------------------------------------


class TestDeployPlanHasChanges:
    def test_has_changes_false_when_all_no_op(self):
        """has_changes is False when every action is NO_OP and no orphans (line 50)."""
        plan = DeployPlan(
            page_actions=[
                PageAction(
                    filepath=Path("a.md"),
                    rel_path="a.md",
                    action="NO_OP",
                    title="A",
                    current_hash="sha256:x",
                    stored_hash="sha256:x",
                    page_id="1",
                )
            ],
            orphan_actions=[],
        )
        assert plan.has_changes() is False

    def test_has_changes_true_when_create_present(self):
        """has_changes is True when any action is CREATE."""
        plan = DeployPlan(
            page_actions=[
                PageAction(
                    filepath=Path("a.md"),
                    rel_path="a.md",
                    action="CREATE",
                    title="A",
                    current_hash="sha256:x",
                )
            ]
        )
        assert plan.has_changes() is True

    def test_has_changes_true_when_update_present(self):
        """has_changes is True when any action is UPDATE."""
        plan = DeployPlan(
            page_actions=[
                PageAction(
                    filepath=Path("a.md"),
                    rel_path="a.md",
                    action="UPDATE",
                    title="A",
                    current_hash="sha256:new",
                    stored_hash="sha256:old",
                    page_id="1",
                )
            ]
        )
        assert plan.has_changes() is True

    def test_has_changes_true_when_orphan_present(self):
        """has_changes is True when orphan_actions is non-empty (line 51)."""
        plan = DeployPlan(
            page_actions=[],
            orphan_actions=[OrphanAction(rel_path="docs/gone.md", page_id="99", title="Gone")],
        )
        assert plan.has_changes() is True

    def test_has_changes_false_when_empty_plan(self):
        assert DeployPlan().has_changes() is False


# ---------------------------------------------------------------------------
# DeployPlan.print_summary
# ---------------------------------------------------------------------------


class TestDeployPlanPrintSummary:
    def _capture(self, plan: DeployPlan) -> str:
        import io
        import sys

        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            plan.print_summary()
        finally:
            sys.stdout = old
        return buf.getvalue()

    def test_print_summary_empty_plan(self):
        """Empty plan prints 'No files found' message (lines 68-71)."""
        plan = DeployPlan()
        output = self._capture(plan)
        assert "No files found" in output

    def test_print_summary_create_action(self):
        """CREATE actions show '+' symbol (lines 73-76)."""
        plan = DeployPlan(
            page_actions=[
                PageAction(
                    filepath=Path("new.md"),
                    rel_path="docs/new.md",
                    action="CREATE",
                    title="New Page",
                    current_hash="sha256:x",
                )
            ]
        )
        output = self._capture(plan)
        assert "+" in output
        assert "CREATE" in output
        assert "New Page" in output

    def test_print_summary_update_action(self):
        """UPDATE actions show '~' symbol."""
        plan = DeployPlan(
            page_actions=[
                PageAction(
                    filepath=Path("upd.md"),
                    rel_path="docs/upd.md",
                    action="UPDATE",
                    title="Updated",
                    current_hash="sha256:new",
                    stored_hash="sha256:old",
                    page_id="1",
                )
            ]
        )
        output = self._capture(plan)
        assert "~" in output
        assert "UPDATE" in output

    def test_print_summary_no_op_action(self):
        """NO_OP actions show '·' symbol."""
        plan = DeployPlan(
            page_actions=[
                PageAction(
                    filepath=Path("same.md"),
                    rel_path="docs/same.md",
                    action="NO_OP",
                    title="Unchanged",
                    current_hash="sha256:x",
                    stored_hash="sha256:x",
                    page_id="1",
                )
            ]
        )
        output = self._capture(plan)
        assert "·" in output
        assert "NO-OP" in output

    def test_print_summary_orphan_action(self):
        """Orphan actions show '-' symbol and '(file removed)' (lines 78-81)."""
        plan = DeployPlan(
            orphan_actions=[OrphanAction(rel_path="docs/gone.md", page_id="7", title="Gone Page")]
        )
        output = self._capture(plan)
        assert "ARCHIVE" in output
        assert "file removed" in output
        assert "Gone Page" in output

    def test_print_summary_plan_line_with_all_action_types(self):
        """Plan summary line lists creates, updates, archives, unchanged (lines 83-99)."""
        plan = DeployPlan(
            page_actions=[
                PageAction(Path("c.md"), "c.md", "CREATE", "C", "sha256:c"),
                PageAction(Path("u.md"), "u.md", "UPDATE", "U", "sha256:u", "sha256:old", "1"),
                PageAction(Path("n.md"), "n.md", "NO_OP", "N", "sha256:n", "sha256:n", "2"),
            ],
            orphan_actions=[OrphanAction(rel_path="o.md", page_id="3", title="O")],
        )
        output = self._capture(plan)
        assert "1 to create" in output
        assert "1 to update" in output
        assert "1 to archive" in output
        assert "1 unchanged" in output

    def test_print_summary_shows_run_without_plan_when_changes(self):
        """'Run without --plan to apply.' appears when has_changes() is True (lines 101-103)."""
        plan = DeployPlan(
            page_actions=[PageAction(Path("x.md"), "x.md", "CREATE", "X", "sha256:x")]
        )
        output = self._capture(plan)
        assert "Run without --plan to apply." in output

    def test_print_summary_no_run_prompt_when_all_no_op(self):
        """'Run without --plan' is suppressed when has_changes() is False."""
        plan = DeployPlan(
            page_actions=[
                PageAction(Path("s.md"), "s.md", "NO_OP", "S", "sha256:s", "sha256:s", "1")
            ]
        )
        output = self._capture(plan)
        assert "Run without --plan" not in output


# ---------------------------------------------------------------------------
# _derive_title helper (tested indirectly via compute_plan)
# ---------------------------------------------------------------------------


class TestDeriveTitleViaComputePlan:
    def test_title_from_frontmatter(self, tmp_path):
        """_derive_title returns the frontmatter title when present (lines 112-113).

        The frontmatter parser reads titles from page_meta.title, not a top-level title key.
        """
        docs = tmp_path / "docs"
        docs.mkdir()
        f = _write_md(docs, "guide.md", "---\npage_meta:\n  title: My Guide\n---\n# Content")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions[0].title == "My Guide"

    def test_title_derived_from_stem_when_no_frontmatter(self, tmp_path):
        """_derive_title generates from stem when no frontmatter title (line 117)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f = _write_md(docs, "my-cool-page.md", "# No frontmatter here")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions[0].title == "My Cool Page"

    def test_title_falls_back_on_oserror(self, tmp_path):
        """_derive_title catches OSError and falls back to stem (lines 115-116)."""
        from unittest.mock import patch

        docs = tmp_path / "docs"
        docs.mkdir()
        f = docs / "error-file.md"
        f.write_bytes(b"# content")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            # Patch Path.read_text on the specific instance to raise OSError
            with patch("plan.planner.Path.read_text", side_effect=OSError("disk error")):
                plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions[0].title == "Error File"


# ---------------------------------------------------------------------------
# compute_plan — main logic
# ---------------------------------------------------------------------------


class TestComputePlan:
    def test_create_when_no_state_entry(self, tmp_path):
        """File with no state entry gets CREATE action (lines 150-159)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f = _write_md(docs, "new.md")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert len(plan.page_actions) == 1
        assert plan.page_actions[0].action == "CREATE"
        assert plan.page_actions[0].page_id is None

    def test_update_when_hash_changed(self, tmp_path):
        """File with mismatched hash gets UPDATE action (lines 160-171)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f = _write_md(docs, "changed.md", "# Version 1")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = str(f.relative_to(tmp_path))
            # Set stale hash
            state.set_page(rel, "p1", "Changed", "SP", "s", "sha256:stale")
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions[0].action == "UPDATE"
        assert plan.page_actions[0].page_id == "p1"
        assert plan.page_actions[0].stored_hash == "sha256:stale"

    def test_no_op_when_hash_unchanged(self, tmp_path):
        """File with matching hash gets NO_OP action (lines 172-183)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f = _write_md(docs, "same.md", "# Stable")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = str(f.relative_to(tmp_path))
            current_hash = state.compute_hash(f)
            state.set_page(rel, "p2", "Same", "SP", "s", current_hash)
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions[0].action == "NO_OP"
        assert plan.page_actions[0].stored_hash == current_hash

    def test_no_orphans_when_archive_orphans_false(self, tmp_path):
        """Orphan detection is skipped when archive_orphans=False (line 185)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            # rel_path will be "docs/deleted.md" (relative to cwd=tmp_path)
            deleted = docs / "deleted.md"
            rel = str(deleted.relative_to(tmp_path))
            state.set_page(rel, "old", "Deleted", "SP", "s", "sha256:x")

            # docs_root must be Path("docs") so find_orphans' relative_to check works
            plan = compute_plan(state, [], Path("docs"), archive_orphans=False)
        finally:
            os.chdir(old_cwd)

        assert plan.orphan_actions == []

    def test_orphans_detected_when_archive_orphans_true(self, tmp_path):
        """Orphan entries are added when archive_orphans=True (lines 185-195).

        docs_root must be the relative form matching the rel_path prefix for the
        find_orphans relative_to check to pass.
        """
        docs = tmp_path / "docs"
        docs.mkdir()
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            deleted = docs / "deleted.md"
            rel = str(deleted.relative_to(tmp_path))  # "docs/deleted.md"
            state.set_page(rel, "old-page", "Deleted", "SP", "s", "sha256:x")

            plan = compute_plan(state, [], Path("docs"), archive_orphans=True)
        finally:
            os.chdir(old_cwd)

        assert len(plan.orphan_actions) == 1
        assert plan.orphan_actions[0].page_id == "old-page"
        assert plan.orphan_actions[0].action == "ARCHIVE"

    def test_files_sorted_in_output(self, tmp_path):
        """Files are processed in sorted order (line 140)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        fb = _write_md(docs, "b.md")
        fa = _write_md(docs, "a.md")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [fb, fa], docs)
        finally:
            os.chdir(old_cwd)

        rel_paths = [a.rel_path for a in plan.page_actions]
        assert rel_paths == sorted(rel_paths)

    def test_rel_path_falls_back_to_str_when_outside_cwd(self, tmp_path):
        """ValueError from relative_to falls back to str(filepath) (lines 143-144)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f = _write_md(docs, "page.md")
        state = _make_state(tmp_path)

        # Change to a directory that does NOT contain tmp_path
        old_cwd = os.getcwd()
        os.chdir("/tmp")
        try:
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        # rel_path should be the absolute string, not raise
        assert str(f) == plan.page_actions[0].rel_path

    def test_empty_files_list_produces_empty_plan(self, tmp_path):
        """compute_plan with no files returns empty page_actions."""
        docs = tmp_path / "docs"
        docs.mkdir()
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [], docs)
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions == []
        assert plan.orphan_actions == []
