"""Tests for state.backend module."""

import hashlib
from unittest.mock import Mock, call

import pytest

from ccfm_convert.state.backend import (
    PAGE_PROPERTY_PREFIX,
    STATE_VERSION,
    ContentPropertyBackend,
    _empty_state,
    _key_for_path,
)


def _page_prop(path, entry, version=1):
    """Build a Confluence content-property dict as ``list_content_properties`` returns it."""
    return {
        "key": _key_for_path(path),
        "value": {"path": path, **entry},
        "version": {"number": version},
    }


class TestEmptyState:
    def test_returns_version_and_empty_pages(self):
        state = _empty_state()
        assert state["version"] == STATE_VERSION
        assert state["pages"] == {}


class TestKeyForPath:
    def test_key_uses_expected_prefix_and_length(self):
        key = _key_for_path("docs/example.md")
        assert key.startswith(PAGE_PROPERTY_PREFIX)
        # 16 hex chars after the prefix
        assert len(key) == len(PAGE_PROPERTY_PREFIX) + 16

    def test_key_is_deterministic(self):
        assert _key_for_path("docs/a.md") == _key_for_path("docs/a.md")

    def test_distinct_paths_yield_distinct_keys(self):
        assert _key_for_path("docs/a.md") != _key_for_path("docs/b.md")

    def test_key_matches_sha256_truncation(self):
        path = "any/path.md"
        expected_digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
        assert _key_for_path(path) == f"{PAGE_PROPERTY_PREFIX}{expected_digest}"

    def test_key_handles_non_ascii_path(self):
        """Non-ASCII paths must produce a valid key — locks in the UTF-8 encoding."""
        ascii_key = _key_for_path("docs/cafe.md")
        accented_key = _key_for_path("docs/café.md")
        emoji_key = _key_for_path("docs/🚀.md")
        for key in (ascii_key, accented_key, emoji_key):
            assert key.startswith(PAGE_PROPERTY_PREFIX)
            assert len(key) == len(PAGE_PROPERTY_PREFIX) + 16
            # Hex suffix only — confirms the digest survived the encode round-trip.
            int(key[len(PAGE_PROPERTY_PREFIX) :], 16)
        # Distinct paths still distinct after Unicode encoding.
        assert ascii_key != accented_key != emoji_key


class TestContentPropertyBackendLoad:
    def test_returns_empty_state_when_no_properties(self):
        api = Mock()
        api.list_content_properties.return_value = []
        backend = ContentPropertyBackend(api, "page-123")

        result = backend.load()

        assert result == _empty_state()
        api.list_content_properties.assert_called_once_with("page-123")

    def test_assembles_pages_from_properties(self):
        api = Mock()
        entry = {
            "page_id": "42",
            "title": "Guide",
            "space_key": "DOCS",
            "space_id": "sid",
            "content_hash": "sha256:abc",
            "deployed_at": "2024-01-01T00:00:00+00:00",
        }
        api.list_content_properties.return_value = [_page_prop("docs/guide.md", entry, version=2)]
        backend = ContentPropertyBackend(api, "page-123")

        result = backend.load()

        assert result["version"] == STATE_VERSION
        assert result["pages"] == {"docs/guide.md": entry}
        # Cache stores the version Confluence returned (no off-by-one) and the
        # full value so save() can detect unchanged entries.
        cached = backend._cache[_key_for_path("docs/guide.md")]
        assert cached["version"] == 2
        assert cached["value"] == {"path": "docs/guide.md", **entry}

    def test_handles_multiple_pages(self):
        api = Mock()
        api.list_content_properties.return_value = [
            _page_prop("a.md", {"page_id": "1"}, version=4),
            _page_prop("b.md", {"page_id": "2"}, version=7),
        ]
        backend = ContentPropertyBackend(api, "page-123")

        result = backend.load()

        assert set(result["pages"].keys()) == {"a.md", "b.md"}
        assert result["pages"]["a.md"] == {"page_id": "1"}
        assert result["pages"]["b.md"] == {"page_id": "2"}

    def test_ignores_non_state_properties(self):
        """Lock and other foreign properties on the management page are skipped."""
        api = Mock()
        api.list_content_properties.return_value = [
            {"key": "ccfm-lock", "value": {"locked": True}, "version": {"number": 5}},
            _page_prop("a.md", {"page_id": "1"}),
            {"key": "some-other-app-prop", "value": {}, "version": {"number": 1}},
        ]
        backend = ContentPropertyBackend(api, "page-123")

        result = backend.load()

        assert list(result["pages"].keys()) == ["a.md"]
        # Only the state property is cached; the lock and foreign property are not.
        assert list(backend._cache.keys()) == [_key_for_path("a.md")]

    def test_raises_on_non_dict_value(self):
        api = Mock()
        api.list_content_properties.return_value = [
            {
                "key": _key_for_path("a.md"),
                "value": ["not", "a", "dict"],
                "version": {"number": 1},
            },
        ]
        backend = ContentPropertyBackend(api, "page-123")

        with pytest.raises(ValueError, match="unexpected value type"):
            backend.load()

    def test_raises_when_path_missing_from_value(self):
        api = Mock()
        api.list_content_properties.return_value = [
            {"key": _key_for_path("a.md"), "value": {"page_id": "1"}, "version": {"number": 1}},
        ]
        backend = ContentPropertyBackend(api, "page-123")

        with pytest.raises(ValueError, match="missing a string 'path'"):
            backend.load()

    def test_raises_when_path_is_empty_string(self):
        api = Mock()
        api.list_content_properties.return_value = [
            {
                "key": _key_for_path("a.md"),
                "value": {"path": "", "page_id": "1"},
                "version": {"number": 1},
            },
        ]
        backend = ContentPropertyBackend(api, "page-123")

        with pytest.raises(ValueError, match="missing a string 'path'"):
            backend.load()

    def test_raises_when_version_number_missing(self):
        """A property missing a numeric version surfaces loudly rather than mis-caching.

        Silently loading without a cached version would cause the next save()
        to mis-classify the entry as "new" and POST it, which Confluence
        rejects with a confusing 4xx. Raising here points the user at the
        real cause — a malformed property envelope on the management page.
        """
        api = Mock()
        api.list_content_properties.return_value = [
            {
                "key": _key_for_path("a.md"),
                "value": {"path": "a.md", "page_id": "1"},
                "version": {},
            },
        ]
        backend = ContentPropertyBackend(api, "page-123")

        with pytest.raises(ValueError, match="missing a numeric 'version.number'"):
            backend.load()

    def test_raises_when_version_number_is_non_int(self):
        api = Mock()
        api.list_content_properties.return_value = [
            {
                "key": _key_for_path("a.md"),
                "value": {"path": "a.md", "page_id": "1"},
                "version": {"number": "not-an-int"},
            },
        ]
        backend = ContentPropertyBackend(api, "page-123")

        with pytest.raises(ValueError, match="missing a numeric 'version.number'"):
            backend.load()

    def test_load_resets_cache(self):
        """Repeated load() calls don't accumulate stale cache entries."""
        api = Mock()
        api.list_content_properties.side_effect = [
            [_page_prop("a.md", {"page_id": "1"}, version=3)],
            [],  # second load: no properties
        ]
        backend = ContentPropertyBackend(api, "page-123")

        backend.load()
        assert backend._cache  # populated from first load
        backend.load()
        assert backend._cache == {}


class TestContentPropertyBackendSave:
    def test_save_creates_new_property_when_absent(self):
        api = Mock()
        backend = ContentPropertyBackend(api, "page-123")
        # No load() — cache is empty, so all paths look new.

        backend.save({"version": "1", "pages": {"a.md": {"page_id": "1"}}})

        # POST (no version kwarg) for new property.
        api.set_content_property.assert_called_once_with(
            "page-123",
            _key_for_path("a.md"),
            {"path": "a.md", "page_id": "1"},
        )
        api.delete_content_property.assert_not_called()

    def test_save_updates_existing_property_with_version_plus_one(self):
        api = Mock()
        api.list_content_properties.return_value = [
            _page_prop("a.md", {"page_id": "1"}, version=4),
        ]
        backend = ContentPropertyBackend(api, "page-123")
        backend.load()

        backend.save({"version": "1", "pages": {"a.md": {"page_id": "1", "title": "New"}}})

        api.set_content_property.assert_called_once_with(
            "page-123",
            _key_for_path("a.md"),
            {"path": "a.md", "page_id": "1", "title": "New"},
            version=5,
        )

    def test_save_skips_unchanged_entries(self):
        """An entry whose value matches the cached value is not re-written.

        This keeps the API-call count proportional to the *changes* in a deploy,
        not the size of state — important for runs that update only a few
        pages out of many tracked.
        """
        api = Mock()
        unchanged_entry = {"page_id": "1", "title": "Same", "content_hash": "sha256:abc"}
        api.list_content_properties.return_value = [
            _page_prop("a.md", unchanged_entry, version=4),
            _page_prop("b.md", {"page_id": "2"}, version=2),
        ]
        backend = ContentPropertyBackend(api, "page-123")
        backend.load()

        backend.save(
            {
                "version": "1",
                "pages": {
                    "a.md": unchanged_entry,  # identical → no write
                    "b.md": {"page_id": "2", "title": "Changed"},  # different → PUT
                },
            }
        )

        # Only the changed entry triggers a write.
        api.set_content_property.assert_called_once_with(
            "page-123",
            _key_for_path("b.md"),
            {"path": "b.md", "page_id": "2", "title": "Changed"},
            version=3,
        )
        api.delete_content_property.assert_not_called()

    def test_save_deletes_properties_no_longer_in_data(self):
        api = Mock()
        api.list_content_properties.return_value = [
            _page_prop("keep.md", {"page_id": "1"}, version=2),
            _page_prop("drop.md", {"page_id": "2"}, version=3),
        ]
        backend = ContentPropertyBackend(api, "page-123")
        backend.load()

        backend.save({"version": "1", "pages": {"keep.md": {"page_id": "1"}}})

        api.delete_content_property.assert_called_once_with("page-123", _key_for_path("drop.md"))
        # keep.md is unchanged → no write.
        api.set_content_property.assert_not_called()

    def test_save_handles_mixed_create_update_delete(self):
        api = Mock()
        api.list_content_properties.return_value = [
            _page_prop("update.md", {"page_id": "u-old"}, version=1),
            _page_prop("delete.md", {"page_id": "d"}, version=1),
        ]
        backend = ContentPropertyBackend(api, "page-123")
        backend.load()

        backend.save(
            {
                "version": "1",
                "pages": {
                    "update.md": {"page_id": "u-new"},
                    "create.md": {"page_id": "c"},
                },
            }
        )

        # update.md → PUT with version 2, create.md → POST (no version).
        update_call = call(
            "page-123",
            _key_for_path("update.md"),
            {"path": "update.md", "page_id": "u-new"},
            version=2,
        )
        create_call = call(
            "page-123",
            _key_for_path("create.md"),
            {"path": "create.md", "page_id": "c"},
        )
        assert update_call in api.set_content_property.call_args_list
        assert create_call in api.set_content_property.call_args_list
        assert api.set_content_property.call_count == 2

        api.delete_content_property.assert_called_once_with("page-123", _key_for_path("delete.md"))

    def test_save_with_empty_pages_deletes_everything(self):
        api = Mock()
        api.list_content_properties.return_value = [
            _page_prop("a.md", {"page_id": "1"}, version=1),
            _page_prop("b.md", {"page_id": "2"}, version=1),
        ]
        backend = ContentPropertyBackend(api, "page-123")
        backend.load()

        backend.save({"version": "1", "pages": {}})

        assert api.delete_content_property.call_count == 2
        api.set_content_property.assert_not_called()

    def test_save_resets_cache(self):
        """After save(), the cache is cleared so a follow-up save() must re-load()."""
        api = Mock()
        api.list_content_properties.return_value = [
            _page_prop("a.md", {"page_id": "1"}, version=3),
        ]
        backend = ContentPropertyBackend(api, "page-123")
        backend.load()
        assert backend._cache  # populated

        backend.save({"version": "1", "pages": {"a.md": {"page_id": "1", "title": "x"}}})

        assert backend._cache == {}

    def test_save_raises_on_non_dict_pages(self):
        api = Mock()
        backend = ContentPropertyBackend(api, "page-123")

        with pytest.raises(ValueError, match="'pages' must be a dict"):
            backend.save({"version": "1", "pages": ["not", "a", "dict"]})

    def test_save_raises_when_entry_is_not_a_dict(self):
        """Each per-page entry must be a dict — non-dict entries are caller bugs."""
        api = Mock()
        backend = ContentPropertyBackend(api, "page-123")

        with pytest.raises(ValueError, match="not a dict"):
            backend.save({"version": "1", "pages": {"a.md": "not-a-dict"}})

    def test_save_raises_when_entry_contains_path_key(self):
        """An entry that carries its own 'path' field is ambiguous — refuse to write.

        The dict key is the relative path; the value is the metadata. A 'path'
        inside the entry would either silently override the explicit one
        (corrupting the path → entry mapping on the next load) or be silently
        ignored. Loud refusal is safer.
        """
        api = Mock()
        backend = ContentPropertyBackend(api, "page-123")

        with pytest.raises(ValueError, match="must not contain its own 'path' key"):
            backend.save(
                {
                    "version": "1",
                    "pages": {
                        "actual.md": {"path": "wrong.md", "page_id": "1"},
                    },
                }
            )
        api.set_content_property.assert_not_called()

    def test_save_raises_when_pages_key_missing(self):
        """A state dict with no 'pages' key is rejected — never silently no-ops.

        Earlier behaviour defaulted missing 'pages' to {}. With the cache-bearing
        save logic, that default would silently delete every tracked property
        — too destructive to accept as the meaning of "no pages key". An
        explicit empty dict (``{"pages": {}}``) is still accepted as the
        legitimate way to express "no entries", since callers reaching that
        path know they're asking to clear state.
        """
        api = Mock()
        backend = ContentPropertyBackend(api, "page-123")

        with pytest.raises(ValueError, match="must contain a 'pages' key"):
            backend.save({"version": "1"})
        api.set_content_property.assert_not_called()
        api.delete_content_property.assert_not_called()

    def test_save_with_explicit_empty_pages_against_cache_deletes_everything(self):
        """Explicit empty 'pages' against a populated cache is a legitimate "clear all".

        This is the difference from the missing-key case above: an explicit
        ``{"pages": {}}`` IS allowed to delete everything (used by ``state
        push`` of an empty state file, for example). Verifying this lets us
        catch a regression where the missing-key guard is broadened to also
        block legitimate clears.
        """
        api = Mock()
        api.list_content_properties.return_value = [
            _page_prop("a.md", {"page_id": "1"}, version=1),
        ]
        backend = ContentPropertyBackend(api, "page-123")
        backend.load()

        backend.save({"version": "1", "pages": {}})

        api.delete_content_property.assert_called_once_with("page-123", _key_for_path("a.md"))
        api.set_content_property.assert_not_called()

    def test_save_prints_success_message(self, capsys):
        api = Mock()
        backend = ContentPropertyBackend(api, "page-123")

        backend.save({"version": "1", "pages": {}})

        captured = capsys.readouterr()
        assert "CCFM State updated successfully" in captured.out
