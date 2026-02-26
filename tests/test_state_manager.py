"""Tests for state.manager.StateManager."""

import hashlib
import json
from pathlib import Path

import pytest

from state.manager import StateManager


@pytest.fixture
def state_path(tmp_path):
    """Return a path for a state file inside tmp_path."""
    return tmp_path / ".ccfm-state.json"


@pytest.fixture
def manager(state_path):
    """Return a fresh StateManager with no prior state."""
    return StateManager(state_path)


class TestInit:
    def test_initial_state_has_version_and_empty_pages(self, manager):
        assert manager._state["version"] == StateManager.STATE_VERSION
        assert manager._state["pages"] == {}

    def test_path_is_stored(self, state_path, manager):
        assert manager.path == state_path


class TestLoad:
    def test_load_no_op_when_file_absent(self, manager):
        """load() is silent when the state file does not exist (line 32-33)."""
        manager.load()
        assert manager._state["pages"] == {}

    def test_load_reads_existing_file(self, state_path, manager):
        """load() deserialises JSON from disk (lines 34-36)."""
        existing = {
            "version": "1",
            "pages": {
                "docs/guide.md": {
                    "page_id": "123",
                    "title": "Guide",
                    "space_key": "DOCS",
                    "space_id": "sid",
                    "content_hash": "sha256:abc",
                    "deployed_at": "2024-01-01T00:00:00+00:00",
                }
            },
        }
        state_path.write_text(json.dumps(existing), encoding="utf-8")
        manager.load()

        assert manager._state["pages"]["docs/guide.md"]["page_id"] == "123"
        assert manager._state["version"] == "1"

    def test_load_raises_on_invalid_schema(self, state_path, manager):
        """load() raises ValueError when state file has unexpected schema (line 38)."""
        state_path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
        with pytest.raises(ValueError, match="unexpected schema"):
            manager.load()


class TestSave:
    def test_save_writes_json_to_disk(self, state_path, manager):
        """save() writes state JSON via atomic rename (lines 40-42)."""
        manager.set_page(
            rel_path="docs/page.md",
            page_id="p1",
            title="Page",
            space_key="DOCS",
            space_id="s1",
            content_hash="sha256:deadbeef",
        )
        manager.save()

        assert state_path.exists()
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["pages"]["docs/page.md"]["page_id"] == "p1"

    def test_save_uses_atomic_rename(self, state_path, manager):
        """Tmp file is cleaned up after rename (atomic write pattern)."""
        manager.save()
        tmp = state_path.with_suffix(".json.tmp")
        # After save the tmp file must NOT exist (it was renamed)
        assert not tmp.exists()
        assert state_path.exists()

    def test_save_is_sorted_keys(self, state_path, manager):
        """save() uses sort_keys=True for deterministic output."""
        manager.set_page("b.md", "2", "B", "DOCS", "s1", "sha256:00")
        manager.set_page("a.md", "1", "A", "DOCS", "s1", "sha256:00")
        manager.save()

        raw = state_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        keys = list(data["pages"].keys())
        assert keys == sorted(keys)


class TestGetPage:
    def test_get_page_returns_none_when_not_tracked(self, manager):
        """get_page returns None for unknown paths (line 50)."""
        assert manager.get_page("docs/nonexistent.md") is None

    def test_get_page_returns_entry_when_tracked(self, manager):
        manager.set_page("docs/foo.md", "42", "Foo", "SP", "sid", "sha256:ff")
        entry = manager.get_page("docs/foo.md")
        assert entry is not None
        assert entry["page_id"] == "42"


class TestSetPage:
    def test_set_page_creates_entry(self, manager):
        """set_page stores all expected fields (line 62)."""
        manager.set_page(
            rel_path="docs/new.md",
            page_id="99",
            title="New",
            space_key="TST",
            space_id="s99",
            content_hash="sha256:123abc",
        )
        entry = manager._state["pages"]["docs/new.md"]
        assert entry["page_id"] == "99"
        assert entry["title"] == "New"
        assert entry["space_key"] == "TST"
        assert entry["space_id"] == "s99"
        assert entry["content_hash"] == "sha256:123abc"
        assert "deployed_at" in entry

    def test_set_page_overwrites_existing(self, manager):
        manager.set_page("docs/a.md", "1", "Old Title", "SP", "s", "sha256:old")
        manager.set_page("docs/a.md", "2", "New Title", "SP", "s", "sha256:new")
        assert manager.get_page("docs/a.md")["title"] == "New Title"


class TestRemovePage:
    def test_remove_page_deletes_tracked_entry(self, manager):
        """remove_page pops the entry from pages (line 73)."""
        manager.set_page("docs/rm.md", "10", "Rm", "SP", "s", "sha256:x")
        manager.remove_page("docs/rm.md")
        assert manager.get_page("docs/rm.md") is None

    def test_remove_page_no_op_when_not_tracked(self, manager):
        """remove_page is silent when the path is not in state."""
        # Should not raise
        manager.remove_page("docs/ghost.md")


class TestAllPages:
    def test_all_pages_returns_shallow_copy(self, manager):
        """all_pages returns a new dict (shallow copy) of the pages (line 78)."""
        manager.set_page("docs/a.md", "1", "A", "SP", "s", "sha256:a")
        pages = manager.all_pages
        assert "docs/a.md" in pages
        # Adding a new key to the copy must NOT appear in the internal state
        pages["docs/extra.md"] = {"page_id": "999"}
        assert manager.get_page("docs/extra.md") is None

    def test_all_pages_empty_when_no_entries(self, manager):
        assert manager.all_pages == {}


class TestComputeHash:
    def test_compute_hash_returns_sha256_prefixed_hex(self, manager, tmp_path):
        """compute_hash returns sha256:<hex> (lines 89-90)."""
        f = tmp_path / "sample.txt"
        f.write_bytes(b"hello world")
        expected = "sha256:" + hashlib.sha256(b"hello world").hexdigest()
        assert manager.compute_hash(f) == expected

    def test_compute_hash_differs_for_different_content(self, manager, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"abc")
        f2.write_bytes(b"xyz")
        assert manager.compute_hash(f1) != manager.compute_hash(f2)


class TestHasChanged:
    def test_has_changed_true_when_not_tracked(self, manager, tmp_path):
        """has_changed is True for untracked files (lines 95-97)."""
        f = tmp_path / "untracked.md"
        f.write_bytes(b"# Hello")
        assert manager.has_changed("docs/untracked.md", f) is True

    def test_has_changed_false_when_hash_matches(self, manager, tmp_path):
        """has_changed is False when stored hash equals current hash (line 98)."""
        f = tmp_path / "same.md"
        f.write_bytes(b"# Content")
        current_hash = manager.compute_hash(f)
        manager.set_page("docs/same.md", "1", "Same", "SP", "s", current_hash)
        assert manager.has_changed("docs/same.md", f) is False

    def test_has_changed_true_when_content_differs(self, manager, tmp_path):
        """has_changed is True when stored hash differs from current hash."""
        f = tmp_path / "changed.md"
        f.write_bytes(b"# Old")
        old_hash = manager.compute_hash(f)
        manager.set_page("docs/changed.md", "1", "Changed", "SP", "s", old_hash)
        # Overwrite with new content
        f.write_bytes(b"# New")
        assert manager.has_changed("docs/changed.md", f) is True


class TestFindOrphans:
    def test_find_orphans_empty_when_all_files_present(self, manager, tmp_path):
        """No orphans when all tracked files still exist on disk (lines 111-127).

        find_orphans uses Path(rel_path).relative_to(docs_root) so docs_root must be
        a relative path that matches the prefix of rel_path.
        """
        docs = tmp_path / "docs"
        docs.mkdir()
        f = docs / "page.md"
        f.write_bytes(b"# Page")

        import os

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = str(f.relative_to(tmp_path))  # "docs/page.md"
            manager.set_page(rel, "1", "Page", "SP", "s", "sha256:x")
            # docs_root must be relative so Path(rel_path).relative_to(docs_root) works
            orphans = manager.find_orphans([f], Path("docs"))
        finally:
            os.chdir(old_cwd)

        assert orphans == []

    def test_find_orphans_detects_deleted_file(self, manager, tmp_path):
        """Orphan is returned for a tracked file no longer on disk."""
        docs = tmp_path / "docs"
        docs.mkdir()
        deleted = docs / "deleted.md"

        import os

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = str(deleted.relative_to(tmp_path))  # "docs/deleted.md"
            manager.set_page(rel, "42", "Deleted", "SP", "s", "sha256:gone")
            # Pass no current files — deleted.md is absent
            orphans = manager.find_orphans([], Path("docs"))
        finally:
            os.chdir(old_cwd)

        assert rel in orphans

    def test_find_orphans_ignores_entries_outside_docs_root(self, manager, tmp_path):
        """Pages tracked outside docs_root are not flagged as orphans."""
        docs = tmp_path / "docs"
        docs.mkdir()
        other = tmp_path / "other"
        other.mkdir()

        import os

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            other_file = other / "unrelated.md"
            rel = str(other_file.relative_to(tmp_path))  # "other/unrelated.md"
            manager.set_page(rel, "99", "Unrelated", "SP", "s", "sha256:xx")
            # docs_root is "docs" — entry is under "other", not under "docs"
            orphans = manager.find_orphans([], Path("docs"))
        finally:
            os.chdir(old_cwd)

        assert orphans == []

    def test_find_orphans_filepath_not_under_cwd_uses_absolute(self, manager, tmp_path):
        """_to_rel falls back to absolute string when relative_to(cwd) raises ValueError."""
        docs = tmp_path / "docs"
        docs.mkdir()
        present = docs / "present.md"
        present.write_bytes(b"x")

        import os

        old_cwd = os.getcwd()
        # Change to a directory that does NOT contain tmp_path
        os.chdir("/tmp")
        try:
            # present is absolute and NOT relative to /tmp cwd,
            # so _to_rel returns str(present) instead of raising.
            # "some/other.md" is not relative to Path("docs") so not flagged as orphan.
            manager.set_page("some/other.md", "7", "Other", "SP", "s", "sha256:x")
            orphans = manager.find_orphans([present], Path("docs"))
            assert orphans == []
        finally:
            os.chdir(old_cwd)

    def test_find_orphans_absolute_docs_root_under_cwd(self, manager, tmp_path):
        """find_orphans works when docs_root is absolute but under cwd (lines 133-136)."""
        import os

        docs = tmp_path / "docs"
        docs.mkdir()

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = "docs/gone.md"
            manager.set_page(rel, "55", "Gone", "SP", "s", "sha256:x")
            # Pass absolute docs_root that IS under cwd — normalises to "docs"
            orphans = manager.find_orphans([], docs.resolve())
        finally:
            os.chdir(old_cwd)

        assert rel in orphans

    def test_find_orphans_absolute_docs_root_outside_cwd(self, manager):
        """find_orphans falls back gracefully when absolute docs_root not under cwd (lines 135-136).

        When docs_root cannot be made relative to cwd, it is used as-is. Stored
        rel_paths (relative strings) cannot be relative_to an unrelated absolute
        path, so they are silently skipped — no orphans are reported.
        """
        # Use a known absolute path that is definitely not under cwd
        abs_docs_root = Path("/tmp/totally-unrelated-dir")
        manager.set_page("docs/page.md", "1", "Page", "SP", "s", "sha256:x")
        # Should not raise; returns [] because rel_path can't be relative to abs_docs_root
        orphans = manager.find_orphans([], abs_docs_root)
        assert orphans == []
