"""Deploy plan computation — show what CCFM would do without deploying.

Usage:
    plan = compute_plan(state, files, docs_root)
    plan.print_summary()
    if plan.has_changes():
        # proceed with apply
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ccfm_convert.deploy.frontmatter import parse_frontmatter
from ccfm_convert.state.manager import StateManager

if TYPE_CHECKING:
    from ccfm_convert.deploy.dependencies import DependencyGraph


@dataclass
class PageAction:
    """A planned action for a single markdown file."""

    filepath: Path
    rel_path: str
    action: Literal["add", "change", "no-op"]
    title: str
    current_hash: str
    stored_hash: str | None = None
    page_id: str | None = None  # None for add actions


@dataclass
class DestroyAction:
    """A planned destroy for a page whose source was deleted or has deploy_page: false."""

    rel_path: str
    page_id: str
    title: str
    action: Literal["destroy"] = field(default="destroy")


@dataclass
class DeployPlan:
    """The complete set of actions CCFM would take on the next apply."""

    page_actions: list[PageAction] = field(default_factory=list)
    destroy_actions: list[DestroyAction] = field(default_factory=list)
    dependency_graph: DependencyGraph | None = None

    def has_changes(self) -> bool:
        """Return True if any deployable action exists (excludes no-op)."""
        return any(a.action != "no-op" for a in self.page_actions) or bool(self.destroy_actions)

    def print_summary(self) -> None:
        """Print a terraform-style plan summary to stdout."""
        _SYMBOLS = {"add": "+", "change": "~"}

        actionable = [a for a in self.page_actions if a.action != "no-op"]
        has_any = bool(actionable) or bool(self.destroy_actions)

        if not has_any:
            no_ops = sum(1 for a in self.page_actions if a.action == "no-op")
            if no_ops:
                print("\nNo changes. Your Confluence pages are up to date.")
            else:
                print("\nNo files found to process.")
            print()
            return

        # Reorder actionable items by dependency graph when available
        if self.dependency_graph and len(actionable) > 1:
            order_index = {f: i for i, f in enumerate(self.dependency_graph.order)}
            actionable.sort(key=lambda a: order_index.get(a.filepath, len(order_index)))

        print("\nccfm will perform the following actions:\n")

        for action in actionable:
            symbol = _SYMBOLS[action.action]
            label = f"({action.action})"
            print(f'  {symbol} {action.rel_path:<40} {label:<12} "{action.title}"')

        for destroy in self.destroy_actions:
            print(f'  - {destroy.rel_path:<40} {"(destroy)":<12} "{destroy.title}"')

        adds = sum(1 for a in self.page_actions if a.action == "add")
        changes = sum(1 for a in self.page_actions if a.action == "change")
        no_ops = sum(1 for a in self.page_actions if a.action == "no-op")
        destroys = len(self.destroy_actions)

        parts = []
        if adds:
            parts.append(f"{adds} to add")
        if changes:
            parts.append(f"{changes} to change")
        if destroys:
            parts.append(f"{destroys} to destroy")
        if no_ops:
            parts.append(f"{no_ops} unchanged")

        print()
        print(f"Plan: {', '.join(parts)}.")

        # Dependency information
        if self.dependency_graph:
            graph = self.dependency_graph
            if graph.cycles:
                for cycle in graph.cycles:
                    chain = " → ".join(cycle)
                    print(f"  ⚠️  Circular dependency: {chain} (deploying in file order)")
            if graph.unresolved:
                for title, deps in graph.unresolved.items():
                    for dep in deps:
                        print(f'  ⚠️  Unresolved link: "{title}" links to "{dep}"')
        print()


def _read_deploy_flag(filepath: Path) -> bool:
    """Return the deploy_page frontmatter value for *filepath* (default True)."""
    try:
        content = filepath.read_text(encoding="utf-8")
        metadata, _ = parse_frontmatter(content)
        return metadata.get("deploy_page", True)
    except OSError:
        return True


def _derive_title(filepath: Path) -> str:
    """Derive a page title from a markdown file — reads frontmatter if present,
    otherwise generates from the filename stem (same logic as deploy_page)."""
    try:
        content = filepath.read_text(encoding="utf-8")
        metadata, _ = parse_frontmatter(content)
        if metadata.get("title"):
            return metadata["title"]
    except OSError:
        pass
    return filepath.stem.replace("-", " ").title()


def compute_plan(
    state: StateManager,
    files: list[Path],
    docs_root: Path,
    force: bool = False,
) -> DeployPlan:
    """Compute the full deploy plan by comparing files on disk against stored state.

    Each file is classified as:
      add     — no state entry exists (never deployed), or force=True
      change  — state exists but content hash has changed
      no-op   — state exists and hash is unchanged

    Files tracked in state but absent from disk are added as destroy actions.
    Directory container pages are also destroyed when no files remain under them.
    """
    plan = DeployPlan()

    cwd = Path.cwd()

    for filepath in sorted(files):
        try:
            rel_path = str(filepath.relative_to(cwd))
        except ValueError:
            rel_path = str(filepath)

        # Check deploy_page frontmatter before planning any action
        if not _read_deploy_flag(filepath):
            entry = state.get_page(rel_path)
            if entry is not None:
                title = _derive_title(filepath)
                plan.destroy_actions.append(
                    DestroyAction(
                        rel_path=rel_path,
                        page_id=entry["page_id"],
                        title=title,
                    )
                )
            continue

        current_hash = state.compute_hash(filepath)
        entry = state.get_page(rel_path)
        title = _derive_title(filepath)

        if force or entry is None:
            plan.page_actions.append(
                PageAction(
                    filepath=filepath,
                    rel_path=rel_path,
                    action="add",
                    title=title,
                    current_hash=current_hash,
                )
            )
        elif entry["content_hash"] != current_hash:
            plan.page_actions.append(
                PageAction(
                    filepath=filepath,
                    rel_path=rel_path,
                    action="change",
                    title=title,
                    current_hash=current_hash,
                    stored_hash=entry["content_hash"],
                    page_id=entry["page_id"],
                )
            )
        else:
            plan.page_actions.append(
                PageAction(
                    filepath=filepath,
                    rel_path=rel_path,
                    action="no-op",
                    title=title,
                    current_hash=current_hash,
                    stored_hash=entry["content_hash"],
                    page_id=entry["page_id"],
                )
            )

    # Destroy detection — find orphaned pages and empty containers
    # 1. Orphaned .md files (in state but not on disk)
    for rel_path in state.find_orphans(files, docs_root):
        entry = state.get_page(rel_path)
        if entry:
            plan.destroy_actions.append(
                DestroyAction(
                    rel_path=rel_path,
                    page_id=entry["page_id"],
                    title=entry["title"],
                )
            )

    # 2. Orphaned directory containers (content_hash == "", no .md files remain under them)
    current_rel_paths = {a.rel_path for a in plan.page_actions}
    all_pages = state.all_pages
    for rel_path, entry in all_pages.items():
        if rel_path.endswith(".md"):
            continue
        if entry.get("content_hash") != "":
            continue
        # Check if any tracked .md file still exists under this directory
        has_children = any(
            child_path.startswith(rel_path + "/") for child_path in current_rel_paths
        )
        if not has_children:
            plan.destroy_actions.append(
                DestroyAction(
                    rel_path=rel_path,
                    page_id=entry["page_id"],
                    title=entry["title"],
                )
            )

    # Sort destroys deepest-first (children before parents)
    plan.destroy_actions.sort(key=lambda a: a.rel_path.count("/"), reverse=True)

    return plan
