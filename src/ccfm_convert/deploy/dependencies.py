"""Dependency graph resolution for CCFM page deployments.

Scans markdown files for internal page links ([text](<Page Title>)), builds a
dependency graph, and produces a topologically sorted deployment order so that
linked pages exist before pages that reference them.

No API calls — pure file/text analysis.
"""

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from ccfm_convert.adf.inline import PAGE_LINK_PATTERN
from ccfm_convert.deploy.frontmatter import parse_frontmatter


@dataclass
class DependencyGraph:
    """Result of dependency analysis across a set of markdown files."""

    order: list[Path] = field(default_factory=list)
    """Topologically sorted deployment order (dependencies first)."""

    cycles: list[list[str]] = field(default_factory=list)
    """Detected dependency cycles as lists of page title chains."""

    unresolved: dict[str, list[str]] = field(default_factory=dict)
    """Map of page title -> list of linked titles not found in the file set."""


def _derive_title(filepath: Path) -> str:
    """Derive a page title from frontmatter, falling back to the filename stem."""
    try:
        content = filepath.read_text(encoding="utf-8")
        metadata, _ = parse_frontmatter(content)
        if metadata.get("title"):
            return metadata["title"]
    except OSError:
        pass
    return filepath.stem.replace("-", " ").title()


def extract_page_links(markdown_text: str) -> list[str]:
    """Extract unique page titles referenced via ``[text](<Page Title>)`` syntax.

    Returns a deduplicated list of page titles in order of first appearance.
    """
    seen: set[str] = set()
    titles: list[str] = []
    for _display_text, page_title in PAGE_LINK_PATTERN.findall(markdown_text):
        # Skip external URLs in angle brackets (e.g., [text](<https://...>))
        if page_title.startswith(("http://", "https://")):
            continue
        if page_title not in seen:
            seen.add(page_title)
            titles.append(page_title)
    return titles


def build_title_map(files: list[Path]) -> dict[str, Path]:
    """Map page titles to file paths for a set of markdown files.

    Reads frontmatter from each file to determine the title. Falls back to the
    filename stem (``my-page.md`` → ``My Page``). If two files produce the same
    title, the first one (by list order) wins.
    """
    title_map: dict[str, Path] = {}
    for filepath in files:
        title = _derive_title(filepath)
        if title not in title_map:
            title_map[title] = filepath
    return title_map


def build_dependency_graph(
    files: list[Path],
    container_files: list[Path] | None = None,
) -> DependencyGraph:
    """Build a dependency graph and return a topologically sorted deployment order.

    Uses Kahn's algorithm (BFS). Pages with no incoming dependency edges deploy
    first. If cycles are detected, they are recorded and the cycle participants
    are appended in sorted file order.

    Args:
        files: Markdown files to include in the dependency ordering.
        container_files: Optional ``.page_content.md`` files whose titles should
            be resolvable as link targets but which are **not** included in the
            deploy ordering (they are deployed as part of page hierarchy creation).
    """
    if not files:
        return DependencyGraph()

    title_map = build_title_map(files + (container_files or []))
    file_to_title: dict[Path, str] = {fp: title for title, fp in title_map.items()}

    # Build adjacency lists.
    # dependents[B] = {A} means A depends on B (B must deploy before A).
    # in_degree tracks how many deps must deploy before a given file.
    dependents: dict[Path, set[Path]] = {f: set() for f in files}
    in_degree: dict[Path, int] = dict.fromkeys(files, 0)
    unresolved: dict[str, list[str]] = {}

    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8")
        except OSError:
            continue

        linked_titles = extract_page_links(content)
        title = file_to_title.get(filepath, "")
        seen_deps: set[Path] = set()

        for linked_title in linked_titles:
            dep_file = title_map.get(linked_title)
            if dep_file is None:
                # External/unresolved dependency
                unresolved.setdefault(title, []).append(linked_title)
            elif dep_file not in dependents:
                # Container page — title resolved but not in deploy ordering
                pass
            elif dep_file != filepath and dep_file not in seen_deps:
                # Internal dependency — dep_file must deploy before filepath
                seen_deps.add(dep_file)
                dependents[dep_file].add(filepath)
                in_degree[filepath] += 1

    # Kahn's algorithm: BFS from nodes with no incoming edges
    queue: deque[Path] = deque()
    for f in sorted(files):  # sorted for deterministic output
        if in_degree[f] == 0:
            queue.append(f)

    order: list[Path] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        # Reduce in-degree for files that depend on this node
        for dependent in sorted(dependents[node]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Detect cycles: any remaining files not in order are in cycles
    cycles: list[list[str]] = []
    remaining = [f for f in sorted(files) if f not in set(order)]
    if remaining:
        # Build cycle chains for reporting
        cycle_titles = [file_to_title.get(f, str(f)) for f in remaining]
        cycles.append(cycle_titles)
        # Append cycle members in sorted order
        order.extend(remaining)

    return DependencyGraph(order=order, cycles=cycles, unresolved=unresolved)
