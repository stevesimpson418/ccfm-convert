"""Tests for state.manager.StateManager."""

import hashlib
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from ccfm_convert.state.manager import StateManager


@pytest.fixture
def mock_backend():
    """Return a mock StateBackend."""
    backend = Mock()
    backend.load.return_value = {"version": "1", "pages": {}}
    return backend


@pytest.fixture
def manager(mock_backend):
    """Return a fresh StateManager with a mock backend."""
    return StateManager(mock_backend)


class TestInit:
    def test_initial_state_has_version_and_empty_pages(self, manager):
        assert manager._state["version"] == StateManager.STATE_VERSION
        assert manager._state["pages"] == {}


class TestLoad:
    def test_load_delegates_to_backend(self, manager, mock_backend):
        """load() calls backend.load() and stores the result."""
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
        mock_backend.load.return_value = existing
        manager.load()

        assert manager._state["pages"]["docs/guide.md"]["page_id"] == "123"
        mock_backend.load.assert_called_once()


class TestSave:
    def test_save_delegates_to_backend(self, manager, mock_backend):
        """save() calls backend.save() with the current state."""
        manager.set_page("docs/page.md", "p1", "Page", "DOCS", "s1", "sha256:deadbeef")
        manager.save()

        mock_backend.save.assert_called_once()
        saved_data = mock_backend.save.call_args[0][0]
        assert saved_data["pages"]["docs/page.md"]["page_id"] == "p1"


class TestGetPage:
    def test_get_page_returns_none_when_not_tracked(self, manager):
        assert manager.get_page("docs/nonexistent.md") is None

    def test_get_page_returns_entry_when_tracked(self, manager):
        manager.set_page("docs/foo.md", "42", "Foo", "SP", "sid", "sha256:ff")
        entry = manager.get_page("docs/foo.md")
        assert entry is not None
        assert entry["page_id"] == "42"


class TestSetPage:
    def test_set_page_creates_entry(self, manager):
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
        manager.set_page("docs/rm.md", "10", "Rm", "SP", "s", "sha256:x")
        manager.remove_page("docs/rm.md")
        assert manager.get_page("docs/rm.md") is None

    def test_remove_page_no_op_when_not_tracked(self, manager):
        manager.remove_page("docs/ghost.md")


class TestAllPages:
    def test_all_pages_returns_copy(self, manager):
        manager.set_page("docs/a.md", "1", "A", "SP", "s", "sha256:a")
        pages = manager.all_pages
        assert "docs/a.md" in pages
        pages["docs/extra.md"] = {"page_id": "999"}
        assert manager.get_page("docs/extra.md") is None

    def test_all_pages_deep_copy_prevents_nested_mutation(self, manager):
        manager.set_page("docs/a.md", "1", "A", "SP", "s", "sha256:a")
        pages = manager.all_pages
        pages["docs/a.md"]["page_id"] = "mutated"
        assert manager.get_page("docs/a.md")["page_id"] == "1"

    def test_all_pages_empty_when_no_entries(self, manager):
        assert manager.all_pages == {}


class TestRawState:
    def test_raw_state_returns_full_dict(self, manager):
        manager.set_page("docs/a.md", "1", "A", "SP", "s", "sha256:a")
        raw = manager.raw_state
        assert raw["version"] == StateManager.STATE_VERSION
        assert "docs/a.md" in raw["pages"]

    def test_raw_state_deep_copy_prevents_top_level_mutation(self, manager):
        raw = manager.raw_state
        raw["injected"] = True
        assert "injected" not in manager.raw_state

    def test_raw_state_deep_copy_prevents_nested_mutation(self, manager):
        manager.set_page("docs/a.md", "1", "A", "SP", "s", "sha256:a")
        raw = manager.raw_state
        raw["pages"]["docs/a.md"]["page_id"] = "mutated"
        assert manager.get_page("docs/a.md")["page_id"] == "1"


class TestComputeHash:
    def test_compute_hash_returns_sha256_prefixed_hex(self, manager, tmp_path):
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
        f = tmp_path / "untracked.md"
        f.write_bytes(b"# Hello")
        assert manager.has_changed("docs/untracked.md", f) is True

    def test_has_changed_false_when_hash_matches(self, manager, tmp_path):
        f = tmp_path / "same.md"
        f.write_bytes(b"# Content")
        current_hash = manager.compute_hash(f)
        manager.set_page("docs/same.md", "1", "Same", "SP", "s", current_hash)
        assert manager.has_changed("docs/same.md", f) is False

    def test_has_changed_true_when_content_differs(self, manager, tmp_path):
        f = tmp_path / "changed.md"
        f.write_bytes(b"# Old")
        old_hash = manager.compute_hash(f)
        manager.set_page("docs/changed.md", "1", "Changed", "SP", "s", old_hash)
        f.write_bytes(b"# New")
        assert manager.has_changed("docs/changed.md", f) is True


class TestFindOrphans:
    def test_find_orphans_empty_when_all_files_present(self, manager, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        f = docs / "page.md"
        f.write_bytes(b"# Page")

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = str(f.relative_to(tmp_path))
            manager.set_page(rel, "1", "Page", "SP", "s", "sha256:x")
            orphans = manager.find_orphans([f], Path("docs"))
        finally:
            os.chdir(old_cwd)

        assert orphans == []

    def test_find_orphans_detects_deleted_file(self, manager, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        deleted = docs / "deleted.md"

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = str(deleted.relative_to(tmp_path))
            manager.set_page(rel, "42", "Deleted", "SP", "s", "sha256:gone")
            orphans = manager.find_orphans([], Path("docs"))
        finally:
            os.chdir(old_cwd)

        assert rel in orphans

    def test_find_orphans_ignores_entries_outside_docs_root(self, manager, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        other = tmp_path / "other"
        other.mkdir()

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            other_file = other / "unrelated.md"
            rel = str(other_file.relative_to(tmp_path))
            manager.set_page(rel, "99", "Unrelated", "SP", "s", "sha256:xx")
            orphans = manager.find_orphans([], Path("docs"))
        finally:
            os.chdir(old_cwd)

        assert orphans == []

    def test_find_orphans_filepath_not_under_cwd_uses_absolute(self, manager, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        present = docs / "present.md"
        present.write_bytes(b"x")

        unrelated_cwd = tmp_path.parent / "unrelated_cwd_state"
        unrelated_cwd.mkdir(exist_ok=True)

        old_cwd = os.getcwd()
        os.chdir(unrelated_cwd)
        try:
            manager.set_page("some/other.md", "7", "Other", "SP", "s", "sha256:x")
            orphans = manager.find_orphans([present], Path("docs"))
            assert orphans == []
        finally:
            os.chdir(old_cwd)

    def test_find_orphans_absolute_docs_root_under_cwd(self, manager, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rel = "docs/gone.md"
            manager.set_page(rel, "55", "Gone", "SP", "s", "sha256:x")
            orphans = manager.find_orphans([], docs.resolve())
        finally:
            os.chdir(old_cwd)

        assert rel in orphans

    def test_find_orphans_absolute_docs_root_outside_cwd(self, manager):
        abs_docs_root = Path("/tmp/totally-unrelated-dir")
        manager.set_page("docs/page.md", "1", "Page", "SP", "s", "sha256:x")
        orphans = manager.find_orphans([], abs_docs_root)
        assert orphans == []

    def test_find_orphans_skips_directory_container_entries(self, manager, tmp_path):
        """Non-.md entries (directory container pages) are never reported as orphans."""
        docs = tmp_path / "docs"
        docs.mkdir()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Add a directory container page (no .md extension) and a real md file
            manager.set_page("docs/my-dir", "dir-id", "My Dir", "SP", "s", "")
            manager.set_page("docs/page.md", "pg-id", "Page", "SP", "s", "sha256:x")
            orphans = manager.find_orphans([], Path("docs"))
        finally:
            os.chdir(old_cwd)
        # Only the .md file should be an orphan; the directory entry is skipped
        assert "docs/my-dir" not in orphans
        assert "docs/page.md" in orphans
