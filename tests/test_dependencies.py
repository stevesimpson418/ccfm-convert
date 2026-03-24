"""Tests for deploy dependency graph resolution."""

import textwrap
from pathlib import Path

from ccfm_convert.deploy.dependencies import (
    DependencyGraph,
    build_dependency_graph,
    build_title_map,
    extract_page_links,
    resolve_file_dependencies,
)

# ---------------------------------------------------------------------------
# extract_page_links
# ---------------------------------------------------------------------------


class TestExtractPageLinks:
    def test_single_link(self):
        md = "See [My Team](<My Team Page>) for details."
        assert extract_page_links(md) == ["My Team Page"]

    def test_multiple_links(self):
        md = "See [A](<Page A>) and [B](<Page B>)."
        assert extract_page_links(md) == ["Page A", "Page B"]

    def test_no_links(self):
        md = "Just plain text with **bold** and *italic*."
        assert extract_page_links(md) == []

    def test_ignores_regular_links(self):
        md = "See [Google](https://google.com) for more."
        assert extract_page_links(md) == []

    def test_ignores_regular_links_but_finds_page_links(self):
        md = "See [Google](https://google.com) and [Team](<Team Page>)."
        assert extract_page_links(md) == ["Team Page"]

    def test_ignores_external_urls_in_angle_brackets(self):
        """External URLs in angle brackets are smart links, not page links."""
        md = "See [Example](<https://example.com>) and [Team](<Team Page>)."
        assert extract_page_links(md) == ["Team Page"]

    def test_ignores_http_url_in_angle_brackets(self):
        md = "See [Example](<http://example.com>)."
        assert extract_page_links(md) == []

    def test_deduplicates(self):
        md = "See [A](<Same Page>) and [B](<Same Page>)."
        assert extract_page_links(md) == ["Same Page"]

    def test_link_in_frontmatter_area_still_found(self):
        """extract_page_links scans raw markdown — it doesn't strip frontmatter."""
        md = textwrap.dedent("""\
            ---
            page_meta:
              title: Test
            ---
            See [X](<Linked Page>).
        """)
        assert extract_page_links(md) == ["Linked Page"]

    def test_multiline(self):
        md = textwrap.dedent("""\
            # Heading
            See [A](<Page A>).

            More text.

            Also [B](<Page B>).
        """)
        assert extract_page_links(md) == ["Page A", "Page B"]


# ---------------------------------------------------------------------------
# build_title_map
# ---------------------------------------------------------------------------


class TestBuildTitleMap:
    def test_maps_frontmatter_titles(self, tmp_path):
        f1 = tmp_path / "page_a.md"
        f1.write_text(textwrap.dedent("""\
                ---
                page_meta:
                  title: My Custom Title
                ---
                Content here.
            """))
        result = build_title_map([f1])
        assert result == {"My Custom Title": f1}

    def test_falls_back_to_stem(self, tmp_path):
        f1 = tmp_path / "my-page.md"
        f1.write_text("No frontmatter here.")
        result = build_title_map([f1])
        assert result == {"My Page": f1}

    def test_multiple_files(self, tmp_path):
        f1 = tmp_path / "alpha.md"
        f1.write_text("---\npage_meta:\n  title: Alpha Page\n---\nContent.")
        f2 = tmp_path / "beta.md"
        f2.write_text("No frontmatter.")
        result = build_title_map([f1, f2])
        assert result == {"Alpha Page": f1, "Beta": f2}

    def test_duplicate_titles_first_wins(self, tmp_path):
        f1 = tmp_path / "a.md"
        f1.write_text("---\npage_meta:\n  title: Same Title\n---\nFirst.")
        f2 = tmp_path / "b.md"
        f2.write_text("---\npage_meta:\n  title: Same Title\n---\nSecond.")
        result = build_title_map(sorted([f1, f2]))
        assert result == {"Same Title": f1}

    def test_page_content_md(self, tmp_path):
        """Container page .page_content.md files should be included in title map."""
        f1 = tmp_path / "subdir" / ".page_content.md"
        f1.parent.mkdir()
        f1.write_text("---\npage_meta:\n  title: Container Page\n---\nContent.")
        result = build_title_map([f1])
        assert result == {"Container Page": f1}

    def test_empty_file(self, tmp_path):
        f1 = tmp_path / "empty.md"
        f1.write_text("")
        result = build_title_map([f1])
        assert result == {"Empty": f1}

    def test_unreadable_file_falls_back_to_stem(self, tmp_path):
        f1 = tmp_path / "missing-file.md"
        # File doesn't exist — OSError path in _derive_title
        result = build_title_map([f1])
        assert result == {"Missing File": f1}


# ---------------------------------------------------------------------------
# build_dependency_graph
# ---------------------------------------------------------------------------


class TestBuildDependencyGraph:
    def test_no_dependencies(self, tmp_path):
        f1 = tmp_path / "a.md"
        f1.write_text("---\npage_meta:\n  title: Page A\n---\nNo links.")
        f2 = tmp_path / "b.md"
        f2.write_text("---\npage_meta:\n  title: Page B\n---\nNo links either.")
        graph = build_dependency_graph([f1, f2])
        assert set(graph.order) == {f1, f2}
        assert graph.cycles == []
        assert graph.unresolved == {}

    def test_linear_chain(self, tmp_path):
        """A links to B, B links to C. Deploy order should be C, B, A."""
        fc = tmp_path / "c.md"
        fc.write_text("---\npage_meta:\n  title: Page C\n---\nNo deps.")
        fb = tmp_path / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nSee [C](<Page C>).")
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>).")
        graph = build_dependency_graph([fa, fb, fc])
        assert graph.order == [fc, fb, fa]
        assert graph.cycles == []
        assert graph.unresolved == {}

    def test_diamond_dependency(self, tmp_path):
        """A depends on B and C, both B and C depend on D. D deploys first, A last."""
        fd = tmp_path / "d.md"
        fd.write_text("---\npage_meta:\n  title: Page D\n---\nLeaf.")
        fb = tmp_path / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nSee [D](<Page D>).")
        fc = tmp_path / "c.md"
        fc.write_text("---\npage_meta:\n  title: Page C\n---\nSee [D](<Page D>).")
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>) and [C](<Page C>).")
        graph = build_dependency_graph([fa, fb, fc, fd])
        # D must be first, A must be last
        assert graph.order[0] == fd
        assert graph.order[-1] == fa
        assert graph.cycles == []

    def test_cycle_detection(self, tmp_path):
        """A -> B -> A creates a cycle. Should warn and still produce an order."""
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>).")
        fb = tmp_path / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nSee [A](<Page A>).")
        graph = build_dependency_graph([fa, fb])
        assert len(graph.cycles) == 1
        # Both files should still appear in order
        assert set(graph.order) == {fa, fb}

    def test_cycle_with_non_cycle_nodes(self, tmp_path):
        """C has no deps, A <-> B cycle. C deploys first, then A and B."""
        fc = tmp_path / "c.md"
        fc.write_text("---\npage_meta:\n  title: Page C\n---\nNo deps.")
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>).")
        fb = tmp_path / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nSee [A](<Page A>).")
        graph = build_dependency_graph([fa, fb, fc])
        # C should deploy before the cycle members
        assert graph.order[0] == fc
        assert set(graph.order) == {fa, fb, fc}

    def test_unresolved_external_links(self, tmp_path):
        """Links to pages not in the file set are recorded as unresolved."""
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [X](<External Page>).")
        graph = build_dependency_graph([fa])
        assert graph.order == [fa]
        assert graph.unresolved == {"Page A": ["External Page"]}
        assert graph.cycles == []

    def test_mixed_resolved_and_unresolved(self, tmp_path):
        """A depends on B (resolved) and X (unresolved)."""
        fb = tmp_path / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nLeaf.")
        fa = tmp_path / "a.md"
        fa.write_text(
            "---\npage_meta:\n  title: Page A\n---\n" "See [B](<Page B>) and [X](<Missing Page>)."
        )
        graph = build_dependency_graph([fa, fb])
        assert graph.order == [fb, fa]
        assert graph.unresolved == {"Page A": ["Missing Page"]}

    def test_self_reference_ignored(self, tmp_path):
        """A page linking to itself should not create a cycle."""
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [A](<Page A>).")
        graph = build_dependency_graph([fa])
        assert graph.order == [fa]
        assert graph.cycles == []

    def test_empty_file_list(self):
        graph = build_dependency_graph([])
        assert graph.order == []
        assert graph.cycles == []
        assert graph.unresolved == {}

    def test_unreadable_file_skipped(self, tmp_path):
        """Files that can't be read are included in order but links aren't extracted."""
        fa = tmp_path / "a.md"
        # File doesn't exist — OSError in build_dependency_graph
        graph = build_dependency_graph([fa])
        assert graph.order == [fa]
        assert graph.cycles == []


# ---------------------------------------------------------------------------
# resolve_file_dependencies
# ---------------------------------------------------------------------------


class TestResolveFileDependencies:
    def test_no_deps(self, tmp_path):
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nNo links.")
        result = resolve_file_dependencies(fa, tmp_path)
        assert result == [fa]

    def test_direct_dependency(self, tmp_path):
        fb = tmp_path / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nLeaf.")
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>).")
        result = resolve_file_dependencies(fa, tmp_path)
        assert result == [fb, fa]

    def test_transitive_dependencies(self, tmp_path):
        fc = tmp_path / "c.md"
        fc.write_text("---\npage_meta:\n  title: Page C\n---\nLeaf.")
        fb = tmp_path / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nSee [C](<Page C>).")
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>).")
        result = resolve_file_dependencies(fa, tmp_path)
        assert result == [fc, fb, fa]

    def test_unresolved_deps_excluded(self, tmp_path):
        """Deps not found in docs_root are excluded (warning handled upstream)."""
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [X](<Missing Page>).")
        result = resolve_file_dependencies(fa, tmp_path)
        assert result == [fa]

    def test_nested_directory(self, tmp_path):
        """Files in subdirectories are discovered."""
        sub = tmp_path / "sub"
        sub.mkdir()
        fb = sub / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nLeaf.")
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>).")
        result = resolve_file_dependencies(fa, tmp_path)
        assert result == [fb, fa]

    def test_cycle_handled_gracefully(self, tmp_path):
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>).")
        fb = tmp_path / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nSee [A](<Page A>).")
        result = resolve_file_dependencies(fa, tmp_path)
        # Both should be present, target file last
        assert fa in result
        assert fb in result
        assert result[-1] == fa

    def test_page_content_md_excluded_from_discovery(self, tmp_path):
        """.page_content.md files are not auto-discovered as deployable deps."""
        sub = tmp_path / "sub"
        sub.mkdir()
        pc = sub / ".page_content.md"
        pc.write_text("---\npage_meta:\n  title: Container\n---\nContent.")
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [C](<Container>).")
        result = resolve_file_dependencies(fa, tmp_path)
        # .page_content.md should NOT be in the result — it's a container page
        assert pc not in result
        assert result == [fa]

    def test_target_outside_docs_root(self, tmp_path):
        """Target file not under docs_root is still included."""
        other = tmp_path / "other"
        other.mkdir()
        fa = other / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nNo links.")
        docs = tmp_path / "docs"
        docs.mkdir()
        result = resolve_file_dependencies(fa, docs)
        assert result == [fa]

    def test_unreadable_target_during_bfs(self, tmp_path):
        """If target file is deleted between graph build and BFS, handle gracefully."""
        fb = tmp_path / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nLeaf.")
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>).")

        # Build with both files existing, then delete fa before calling resolve
        # Actually, resolve reads files internally. Instead, test with a file
        # that exists for discovery but whose content disappears.
        # Simplest: create a file, pass it, then it works. The OSError branch
        # in BFS is defensive. We'll use monkeypatch on just the BFS call.
        from unittest.mock import patch

        real_read = Path.read_text
        bfs_entered = {"value": False}

        def selective_read(self, *args, **kwargs):
            # After build_dependency_graph completes, the BFS reads happen.
            # We track by checking if we're past the graph build phase.
            if bfs_entered["value"] and self == fa:
                raise OSError("gone")
            return real_read(self, *args, **kwargs)

        # Patch at module level where resolve_file_dependencies lives
        with patch.object(Path, "read_text", side_effect=selective_read):
            # We can't easily separate phases, so let's just test the simple case:
            # a non-existent target file
            pass

        # Simpler approach: target file that doesn't exist on disk
        missing = tmp_path / "missing.md"
        # It won't be in docs_root rglob results, but will be appended
        result = resolve_file_dependencies(missing, tmp_path)
        # missing file can't be read during BFS -> OSError caught
        assert result[-1] == missing

    def test_returns_graph_info(self, tmp_path):
        """resolve_file_dependencies returns a tuple with graph when requested."""
        fb = tmp_path / "b.md"
        fb.write_text("---\npage_meta:\n  title: Page B\n---\nLeaf.")
        fa = tmp_path / "a.md"
        fa.write_text("---\npage_meta:\n  title: Page A\n---\nSee [B](<Page B>).")
        files, graph = resolve_file_dependencies(fa, tmp_path, return_graph=True)
        assert files == [fb, fa]
        assert isinstance(graph, DependencyGraph)
        assert graph.unresolved == {}
