"""Tests for plan.planner — DeployPlan, PageAction, DestroyAction, compute_plan."""

import os
from pathlib import Path
from unittest.mock import Mock

from ccfm_convert.plan.planner import DeployPlan, DestroyAction, PageAction, compute_plan
from ccfm_convert.state.manager import StateManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(tmp_path) -> StateManager:
    backend = Mock()
    backend.load.return_value = {"version": "1", "pages": {}}
    return StateManager(backend)


def _write_md(directory: Path, name: str, content: str = "# Hello") -> Path:
    f = directory / name
    f.write_text(content, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# DeployPlan.has_changes
# ---------------------------------------------------------------------------


class TestDeployPlanHasChanges:
    def test_has_changes_false_when_all_no_op(self):
        """has_changes is False when every action is no-op and no destroys."""
        plan = DeployPlan(
            page_actions=[
                PageAction(
                    filepath=Path("a.md"),
                    rel_path="a.md",
                    action="no-op",
                    title="A",
                    current_hash="sha256:x",
                    stored_hash="sha256:x",
                    page_id="1",
                )
            ],
            destroy_actions=[],
        )
        assert plan.has_changes() is False

    def test_has_changes_true_when_add_present(self):
        """has_changes is True when any action is add."""
        plan = DeployPlan(
            page_actions=[
                PageAction(
                    filepath=Path("a.md"),
                    rel_path="a.md",
                    action="add",
                    title="A",
                    current_hash="sha256:x",
                )
            ]
        )
        assert plan.has_changes() is True

    def test_has_changes_true_when_change_present(self):
        """has_changes is True when any action is change."""
        plan = DeployPlan(
            page_actions=[
                PageAction(
                    filepath=Path("a.md"),
                    rel_path="a.md",
                    action="change",
                    title="A",
                    current_hash="sha256:new",
                    stored_hash="sha256:old",
                    page_id="1",
                )
            ]
        )
        assert plan.has_changes() is True

    def test_has_changes_true_when_destroy_present(self):
        """has_changes is True when destroy_actions is non-empty."""
        plan = DeployPlan(
            page_actions=[],
            destroy_actions=[DestroyAction(rel_path="docs/gone.md", page_id="99", title="Gone")],
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

    def test_print_summary_no_files(self):
        """Empty plan prints 'No files found' message."""
        plan = DeployPlan()
        output = self._capture(plan)
        assert "No files found" in output

    def test_print_summary_no_changes(self):
        """All no-op plan prints 'up to date' message."""
        plan = DeployPlan(
            page_actions=[
                PageAction(Path("s.md"), "s.md", "no-op", "S", "sha256:s", "sha256:s", "1")
            ]
        )
        output = self._capture(plan)
        assert "up to date" in output
        # no-op files should NOT be listed individually
        assert "s.md" not in output

    def test_print_summary_add_action(self):
        """add actions show '+' symbol."""
        plan = DeployPlan(
            page_actions=[
                PageAction(
                    filepath=Path("new.md"),
                    rel_path="docs/new.md",
                    action="add",
                    title="New Page",
                    current_hash="sha256:x",
                )
            ]
        )
        output = self._capture(plan)
        assert "+" in output
        assert "docs/new.md" in output
        assert "New Page" in output

    def test_print_summary_change_action(self):
        """change actions show '~' symbol."""
        plan = DeployPlan(
            page_actions=[
                PageAction(
                    filepath=Path("upd.md"),
                    rel_path="docs/upd.md",
                    action="change",
                    title="Updated",
                    current_hash="sha256:new",
                    stored_hash="sha256:old",
                    page_id="1",
                )
            ]
        )
        output = self._capture(plan)
        assert "~" in output
        assert "docs/upd.md" in output

    def test_print_summary_destroy_action(self):
        """Destroy actions show '-' symbol and '(destroy)'."""
        plan = DeployPlan(
            destroy_actions=[DestroyAction(rel_path="docs/gone.md", page_id="7", title="Gone Page")]
        )
        output = self._capture(plan)
        assert "-" in output
        assert "docs/gone.md" in output
        assert "Gone Page" in output

    def test_print_summary_plan_line_with_all_action_types(self):
        """Plan summary line lists adds, changes, destroys, unchanged."""
        plan = DeployPlan(
            page_actions=[
                PageAction(Path("c.md"), "c.md", "add", "C", "sha256:c"),
                PageAction(Path("u.md"), "u.md", "change", "U", "sha256:u", "sha256:old", "1"),
                PageAction(Path("n.md"), "n.md", "no-op", "N", "sha256:n", "sha256:n", "2"),
            ],
            destroy_actions=[DestroyAction(rel_path="o.md", page_id="3", title="O")],
        )
        output = self._capture(plan)
        assert "1 to add" in output
        assert "1 to change" in output
        assert "1 to destroy" in output
        assert "1 unchanged" in output

    def test_print_summary_shows_actions_header_when_changes(self):
        """'ccfm will perform the following actions' appears when has_changes() is True."""
        plan = DeployPlan(page_actions=[PageAction(Path("x.md"), "x.md", "add", "X", "sha256:x")])
        output = self._capture(plan)
        assert "ccfm will perform the following actions" in output


# ---------------------------------------------------------------------------
# _derive_title helper (tested indirectly via compute_plan)
# ---------------------------------------------------------------------------


class TestDeriveTitleViaComputePlan:
    def test_title_from_frontmatter(self, tmp_path):
        """_derive_title returns the frontmatter title when present."""
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
        """_derive_title generates from stem when no frontmatter title."""
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
        """_derive_title catches OSError and falls back to stem."""
        from unittest.mock import patch

        docs = tmp_path / "docs"
        docs.mkdir()
        f = docs / "error-file.md"
        f.write_bytes(b"# content")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch(
                "ccfm_convert.plan.planner.Path.read_text", side_effect=OSError("disk error")
            ):
                plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions[0].title == "Error File"


# ---------------------------------------------------------------------------
# compute_plan — main logic
# ---------------------------------------------------------------------------


class TestComputePlan:
    def test_add_when_no_state_entry(self, tmp_path):
        """File with no state entry gets add action."""
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
        assert plan.page_actions[0].action == "add"
        assert plan.page_actions[0].page_id is None

    def test_change_when_hash_changed(self, tmp_path):
        """File with mismatched hash gets change action."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f = _write_md(docs, "changed.md", "# Version 1")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = str(f.relative_to(tmp_path))
            state.set_page(rel, "p1", "Changed", "SP", "s", "sha256:stale")
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions[0].action == "change"
        assert plan.page_actions[0].page_id == "p1"
        assert plan.page_actions[0].stored_hash == "sha256:stale"

    def test_no_op_when_hash_unchanged(self, tmp_path):
        """File with matching hash gets no-op action."""
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

        assert plan.page_actions[0].action == "no-op"
        assert plan.page_actions[0].stored_hash == current_hash

    def test_destroys_detected_by_default(self, tmp_path):
        """Files tracked in state but absent from disk are destroy actions (always on)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            deleted = docs / "deleted.md"
            rel = str(deleted.relative_to(tmp_path))
            state.set_page(rel, "old-page", "Deleted", "SP", "s", "sha256:x")

            plan = compute_plan(state, [], Path("docs"))
        finally:
            os.chdir(old_cwd)

        assert len(plan.destroy_actions) == 1
        assert plan.destroy_actions[0].page_id == "old-page"
        assert plan.destroy_actions[0].action == "destroy"

    def test_force_classifies_existing_as_add(self, tmp_path):
        """force=True makes all files show as add regardless of state."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f = _write_md(docs, "existing.md", "# Content")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = str(f.relative_to(tmp_path))
            current_hash = state.compute_hash(f)
            state.set_page(rel, "p1", "Existing", "SP", "s", current_hash)
            plan = compute_plan(state, [f], docs, force=True)
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions[0].action == "add"

    def test_directory_container_destroyed_when_no_children_remain(self, tmp_path):
        """Directory container pages are destroyed when no .md files remain under them."""
        docs = tmp_path / "docs"
        docs.mkdir()
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            # Track a directory container and its child file in state
            state.set_page("docs/team", "dir-1", "Team", "SP", "s", "")
            state.set_page("docs/team/page.md", "p1", "Page", "SP", "s", "sha256:x")

            # No files on disk — both should be destroyed
            plan = compute_plan(state, [], Path("docs"))
        finally:
            os.chdir(old_cwd)

        destroy_paths = [a.rel_path for a in plan.destroy_actions]
        assert "docs/team/page.md" in destroy_paths
        assert "docs/team" in destroy_paths

    def test_directory_container_kept_when_children_exist(self, tmp_path):
        """Directory container pages are NOT destroyed when children still exist on disk."""
        docs = tmp_path / "docs"
        (docs / "team").mkdir(parents=True)
        f = _write_md(docs / "team", "page.md", "# Content")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = str(f.relative_to(tmp_path))
            current_hash = state.compute_hash(f)
            state.set_page("docs/team", "dir-1", "Team", "SP", "s", "")
            state.set_page(rel, "p1", "Page", "SP", "s", current_hash)

            plan = compute_plan(state, [f], Path("docs"))
        finally:
            os.chdir(old_cwd)

        assert len(plan.destroy_actions) == 0

    def test_destroys_sorted_deepest_first(self, tmp_path):
        """Destroy actions are sorted deepest-first (children before parents)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            state.set_page("docs/a", "d1", "A", "SP", "s", "")
            state.set_page("docs/a/b", "d2", "B", "SP", "s", "")
            state.set_page("docs/a/b/page.md", "p1", "Page", "SP", "s", "sha256:x")

            plan = compute_plan(state, [], Path("docs"))
        finally:
            os.chdir(old_cwd)

        destroy_paths = [a.rel_path for a in plan.destroy_actions]
        assert destroy_paths.index("docs/a/b/page.md") < destroy_paths.index("docs/a/b")
        assert destroy_paths.index("docs/a/b") < destroy_paths.index("docs/a")

    def test_non_md_entry_without_children_destroyed(self, tmp_path):
        """Non-.md state entries without children are destroyed (orphaned containers)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            state.set_page("docs/weird-entry", "p99", "Weird", "SP", "s", "sha256:notempty")

            plan = compute_plan(state, [], Path("docs"))
        finally:
            os.chdir(old_cwd)

        assert any(a.rel_path == "docs/weird-entry" for a in plan.destroy_actions)

    def test_files_sorted_in_output(self, tmp_path):
        """Files are processed in sorted order."""
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
        """ValueError from relative_to falls back to str(filepath)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        f = _write_md(docs, "page.md")
        state = _make_state(tmp_path)

        unrelated_cwd = tmp_path.parent / "unrelated_cwd"
        unrelated_cwd.mkdir(exist_ok=True)

        old_cwd = os.getcwd()
        os.chdir(unrelated_cwd)
        try:
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert str(f) == plan.page_actions[0].rel_path

    # -----------------------------------------------------------------------
    # deploy_page: false → destroy or skip
    # -----------------------------------------------------------------------

    def test_deploy_page_false_with_state_entry_generates_destroy(self, tmp_path):
        """File on disk with deploy_page: false that exists in state → destroy action."""
        docs = tmp_path / "docs"
        docs.mkdir()
        fm = "---\ndeploy_config:\n  deploy_page: false\n---\n# Content"
        f = _write_md(docs, "retired.md", fm)
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = str(f.relative_to(tmp_path))
            state.set_page(rel, "p-old", "Retired", "SP", "s", "sha256:prev")
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert len(plan.page_actions) == 0, "should NOT appear in page_actions"
        assert len(plan.destroy_actions) == 1
        assert plan.destroy_actions[0].page_id == "p-old"
        assert plan.destroy_actions[0].action == "destroy"

    def test_deploy_page_false_without_state_entry_skipped(self, tmp_path):
        """File on disk with deploy_page: false and no state entry → no action at all."""
        docs = tmp_path / "docs"
        docs.mkdir()
        fm = "---\ndeploy_config:\n  deploy_page: false\n---\n# Never deployed"
        f = _write_md(docs, "local-only.md", fm)
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert len(plan.page_actions) == 0
        assert len(plan.destroy_actions) == 0

    def test_deploy_page_true_explicit_unchanged(self, tmp_path):
        """Explicit deploy_page: true behaves same as default (normal add)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        fm = "---\ndeploy_config:\n  deploy_page: true\n---\n# Deploy me"
        f = _write_md(docs, "active.md", fm)
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        assert len(plan.page_actions) == 1
        assert plan.page_actions[0].action == "add"

    def test_container_destroyed_when_only_child_has_deploy_page_false(self, tmp_path):
        """Container page destroyed when its only child has deploy_page: false."""
        docs = tmp_path / "docs"
        (docs / "team").mkdir(parents=True)
        fm = "---\ndeploy_config:\n  deploy_page: false\n---\n# Retired"
        f = _write_md(docs / "team", "page.md", fm)
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = str(f.relative_to(tmp_path))
            state.set_page("docs/team", "dir-1", "Team", "SP", "s", "")
            state.set_page(rel, "p1", "Page", "SP", "s", "sha256:x")
            plan = compute_plan(state, [f], docs)
        finally:
            os.chdir(old_cwd)

        destroy_paths = [a.rel_path for a in plan.destroy_actions]
        assert "docs/team/page.md" in destroy_paths
        assert "docs/team" in destroy_paths
        assert len(plan.page_actions) == 0

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
        assert plan.destroy_actions == []


# ---------------------------------------------------------------------------
# DeployPlan.print_summary — dependency graph display
# ---------------------------------------------------------------------------


class TestPrintSummaryDependencyInfo:
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

    def test_plan_output_ordered_by_dependency_graph(self):
        """Actionable items in plan output follow dependency graph order."""
        from ccfm_convert.deploy.dependencies import DependencyGraph

        fa = Path("a.md")
        fb = Path("b.md")
        fc = Path("c.md")
        # Graph order: c first (dep), then b, then a (depends on b)
        graph = DependencyGraph(order=[fc, fb, fa], cycles=[], unresolved={})
        plan = DeployPlan(
            page_actions=[
                # Alphabetical order in page_actions (as compute_plan produces)
                PageAction(fa, "a.md", "add", "Page A", "sha256:a"),
                PageAction(fb, "b.md", "add", "Page B", "sha256:b"),
                PageAction(fc, "c.md", "add", "Page C", "sha256:c"),
            ],
            dependency_graph=graph,
        )
        output = self._capture(plan)
        lines = [ln for ln in output.split("\n") if ln.strip().startswith("+")]
        assert len(lines) == 3
        assert "c.md" in lines[0]
        assert "b.md" in lines[1]
        assert "a.md" in lines[2]

    def test_shows_cycle_warning(self):
        """Cycles in dependency graph are shown as warnings."""
        from ccfm_convert.deploy.dependencies import DependencyGraph

        graph = DependencyGraph(
            order=[Path("a.md"), Path("b.md")],
            cycles=[["Page A", "Page B"]],
            unresolved={},
        )
        plan = DeployPlan(
            page_actions=[
                PageAction(Path("a.md"), "a.md", "add", "Page A", "sha256:a"),
                PageAction(Path("b.md"), "b.md", "add", "Page B", "sha256:b"),
            ],
            dependency_graph=graph,
        )
        output = self._capture(plan)
        assert "Circular dependency: Page A → Page B" in output
        assert "deploying in file order" in output

    def test_shows_unresolved_warnings(self):
        """Unresolved dependencies are shown as warnings."""
        from ccfm_convert.deploy.dependencies import DependencyGraph

        graph = DependencyGraph(
            order=[Path("a.md")],
            cycles=[],
            unresolved={"Page A": ["Missing Page"]},
        )
        plan = DeployPlan(
            page_actions=[
                PageAction(Path("a.md"), "a.md", "add", "Page A", "sha256:a"),
            ],
            dependency_graph=graph,
        )
        output = self._capture(plan)
        assert 'Unresolved link: "Page A" links to "Missing Page"' in output

    def test_no_dependency_info_when_graph_is_none(self):
        """No dependency output when dependency_graph is not set."""
        plan = DeployPlan(
            page_actions=[
                PageAction(Path("a.md"), "a.md", "add", "Page A", "sha256:a"),
            ],
        )
        output = self._capture(plan)
        assert "Circular" not in output
        assert "Unresolved" not in output


# ---------------------------------------------------------------------------
# .page_content.md change detection
# ---------------------------------------------------------------------------


class TestPageContentChangeDetection:
    """Tests for .page_content.md files in compute_plan."""

    def test_page_content_add_when_no_state_entry(self, tmp_path):
        """.page_content.md with no state entry for its directory → add action."""
        docs = tmp_path / "docs"
        section = docs / "my-section"
        section.mkdir(parents=True)
        pc = section / ".page_content.md"
        pc.write_text("# Section landing page", encoding="utf-8")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [], docs, page_content_files=[pc])
        finally:
            os.chdir(old_cwd)

        pc_actions = [a for a in plan.page_actions if a.filepath.name == ".page_content.md"]
        assert len(pc_actions) == 1
        assert pc_actions[0].action == "add"
        # rel_path uses the directory path (state key), not the file path
        assert pc_actions[0].rel_path == "docs/my-section"

    def test_page_content_change_when_hash_differs(self, tmp_path):
        """.page_content.md with mismatched hash → change action."""
        docs = tmp_path / "docs"
        section = docs / "my-section"
        section.mkdir(parents=True)
        pc = section / ".page_content.md"
        pc.write_text("# Updated content", encoding="utf-8")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            state.set_page("docs/my-section", "p1", "My Section", "SP", "s", "sha256:old")
            plan = compute_plan(state, [], docs, page_content_files=[pc])
        finally:
            os.chdir(old_cwd)

        pc_actions = [a for a in plan.page_actions if a.filepath.name == ".page_content.md"]
        assert len(pc_actions) == 1
        assert pc_actions[0].action == "change"
        assert pc_actions[0].page_id == "p1"
        assert pc_actions[0].stored_hash == "sha256:old"

    def test_page_content_no_op_when_hash_matches(self, tmp_path):
        """.page_content.md with matching hash → no-op action."""
        docs = tmp_path / "docs"
        section = docs / "my-section"
        section.mkdir(parents=True)
        pc = section / ".page_content.md"
        pc.write_text("# Stable content", encoding="utf-8")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            current_hash = state.compute_hash(pc)
            state.set_page("docs/my-section", "p1", "My Section", "SP", "s", current_hash)
            plan = compute_plan(state, [], docs, page_content_files=[pc])
        finally:
            os.chdir(old_cwd)

        pc_actions = [a for a in plan.page_actions if a.filepath.name == ".page_content.md"]
        assert len(pc_actions) == 1
        assert pc_actions[0].action == "no-op"

    def test_page_content_force_classifies_as_add(self, tmp_path):
        """force=True makes .page_content.md show as add regardless of state."""
        docs = tmp_path / "docs"
        section = docs / "my-section"
        section.mkdir(parents=True)
        pc = section / ".page_content.md"
        pc.write_text("# Content", encoding="utf-8")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            current_hash = state.compute_hash(pc)
            state.set_page("docs/my-section", "p1", "My Section", "SP", "s", current_hash)
            plan = compute_plan(state, [], docs, force=True, page_content_files=[pc])
        finally:
            os.chdir(old_cwd)

        pc_actions = [a for a in plan.page_actions if a.filepath.name == ".page_content.md"]
        assert pc_actions[0].action == "add"

    def test_page_content_title_from_frontmatter(self, tmp_path):
        """Title is derived from .page_content.md frontmatter when present."""
        docs = tmp_path / "docs"
        section = docs / "my-section"
        section.mkdir(parents=True)
        pc = section / ".page_content.md"
        pc.write_text("---\npage_meta:\n  title: Custom Title\n---\n# Content", encoding="utf-8")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [], docs, page_content_files=[pc])
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions[0].title == "Custom Title"

    def test_page_content_title_falls_back_to_dir_name(self, tmp_path):
        """Title falls back to parent directory name when no frontmatter title."""
        docs = tmp_path / "docs"
        section = docs / "my-section"
        section.mkdir(parents=True)
        pc = section / ".page_content.md"
        pc.write_text("# No frontmatter here", encoding="utf-8")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [], docs, page_content_files=[pc])
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions[0].title == "my-section"

    def test_page_content_keeps_container_alive_in_orphan_detection(self, tmp_path):
        """Container with .page_content.md in plan is not destroyed as orphan.

        Simulates a round-trip: state written after first apply, then re-planned.
        The container directory path is in both state and page_actions (via
        .page_content.md), so orphan detection must keep it alive.
        """
        docs = tmp_path / "docs"
        section = docs / "my-section"
        section.mkdir(parents=True)
        pc = section / ".page_content.md"
        pc.write_text("# Landing page", encoding="utf-8")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            current_hash = state.compute_hash(pc)
            state.set_page("docs/my-section", "p1", "My Section", "SP", "s", current_hash)
            plan = compute_plan(state, [], docs, page_content_files=[pc])
        finally:
            os.chdir(old_cwd)

        # Container must NOT be destroyed — .page_content.md action uses dir_rel_path
        # which matches the state key, keeping the container alive
        destroy_paths = [a.rel_path for a in plan.destroy_actions]
        assert "docs/my-section" not in destroy_paths
        # And the .page_content.md should be no-op (hash matches)
        pc_actions = [a for a in plan.page_actions if a.filepath.name == ".page_content.md"]
        assert pc_actions[0].action == "no-op"

    def test_page_content_mixed_with_regular_files(self, tmp_path):
        """Plan includes both regular files and .page_content.md actions."""
        docs = tmp_path / "docs"
        section = docs / "my-section"
        section.mkdir(parents=True)
        pc = section / ".page_content.md"
        pc.write_text("# Landing page", encoding="utf-8")
        child = _write_md(section, "child.md", "# Child page")
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [child], docs, page_content_files=[pc])
        finally:
            os.chdir(old_cwd)

        assert len(plan.page_actions) == 2
        actions_by_name = {a.filepath.name: a for a in plan.page_actions}
        assert "child.md" in actions_by_name
        assert ".page_content.md" in actions_by_name
        assert all(a.action == "add" for a in plan.page_actions)

    def test_page_content_none_defaults_to_empty(self, tmp_path):
        """page_content_files=None is treated as empty list."""
        docs = tmp_path / "docs"
        docs.mkdir()
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [], docs, page_content_files=None)
        finally:
            os.chdir(old_cwd)

        assert plan.page_actions == []

    def test_page_content_deploy_page_false_skipped(self, tmp_path):
        """.page_content.md with deploy_page: false is skipped entirely."""
        docs = tmp_path / "docs"
        section = docs / "section"
        section.mkdir(parents=True)
        pc = section / ".page_content.md"
        pc.write_text(
            "---\ndeploy_config:\n  deploy_page: false\n---\n# Skip me",
            encoding="utf-8",
        )
        state = _make_state(tmp_path)

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            plan = compute_plan(state, [], docs, page_content_files=[pc])
        finally:
            os.chdir(old_cwd)

        assert len(plan.page_actions) == 0

    def test_page_content_rel_path_falls_back_when_outside_cwd(self, tmp_path):
        """ValueError from relative_to falls back to str(parent) for .page_content.md."""
        docs = tmp_path / "docs"
        section = docs / "section"
        section.mkdir(parents=True)
        pc = section / ".page_content.md"
        pc.write_text("# Content", encoding="utf-8")
        state = _make_state(tmp_path)

        unrelated_cwd = tmp_path.parent / "unrelated_pc_cwd"
        unrelated_cwd.mkdir(exist_ok=True)

        old_cwd = os.getcwd()
        os.chdir(unrelated_cwd)
        try:
            plan = compute_plan(state, [], docs, page_content_files=[pc])
        finally:
            os.chdir(old_cwd)

        assert len(plan.page_actions) == 1
        # rel_path falls back to str(filepath.parent) when outside cwd
        assert str(section) == plan.page_actions[0].rel_path
