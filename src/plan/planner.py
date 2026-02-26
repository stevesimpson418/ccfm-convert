"""Deploy plan computation — show what CCFM would do without deploying.

Usage:
    plan = compute_plan(state, files, docs_root, archive_orphans=True)
    plan.print_summary()
    if plan.has_changes():
        # proceed with deploy
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from deploy.frontmatter import parse_frontmatter
from state.manager import StateManager


@dataclass
class PageAction:
    """A planned action for a single markdown file."""

    filepath: Path
    rel_path: str
    action: Literal["CREATE", "UPDATE", "NO_OP"]
    title: str
    current_hash: str
    stored_hash: str | None = None
    page_id: str | None = None  # None for CREATE actions


@dataclass
class OrphanAction:
    """A planned archive action for a page whose source file no longer exists."""

    rel_path: str
    page_id: str
    title: str
    action: Literal["ARCHIVE"] = field(default="ARCHIVE")


@dataclass
class DeployPlan:
    """The complete set of actions CCFM would take on the next deploy."""

    page_actions: list[PageAction] = field(default_factory=list)
    orphan_actions: list[OrphanAction] = field(default_factory=list)

    def has_changes(self) -> bool:
        """Return True if any deployable action exists (excludes NO_OP)."""
        return any(a.action != "NO_OP" for a in self.page_actions) or bool(self.orphan_actions)

    def print_summary(self) -> None:
        """Print a terraform-style plan summary to stdout."""
        _SYMBOLS = {"CREATE": "+", "UPDATE": "~", "NO_OP": "·"}
        _LABELS = {"CREATE": "CREATE ", "UPDATE": "UPDATE ", "NO_OP": "NO-OP  "}

        print("\nCCFM Deploy Plan")
        print("═" * 60)
        print()

        all_actions: list[PageAction | OrphanAction] = [
            *self.page_actions,
            *self.orphan_actions,
        ]

        if not all_actions:
            print("  No files found to deploy.")
            print()
            return

        for action in self.page_actions:
            symbol = _SYMBOLS[action.action]
            label = _LABELS[action.action]
            print(f'  {symbol} {action.rel_path:<45} {label}  "{action.title}"')

        for orphan in self.orphan_actions:
            print(f'  - {orphan.rel_path:<45} ARCHIVE  "{orphan.title}"  (file removed)')

        creates = sum(1 for a in self.page_actions if a.action == "CREATE")
        updates = sum(1 for a in self.page_actions if a.action == "UPDATE")
        no_ops = sum(1 for a in self.page_actions if a.action == "NO_OP")
        archives = len(self.orphan_actions)

        parts = []
        if creates:
            parts.append(f"{creates} to create")
        if updates:
            parts.append(f"{updates} to update")
        if archives:
            parts.append(f"{archives} to archive")
        if no_ops:
            parts.append(f"{no_ops} unchanged")

        print()
        print(f"Plan: {', '.join(parts)}.")

        if self.has_changes():
            print()
            print("Run without --plan to apply.")
        print()


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
    archive_orphans: bool = False,
) -> DeployPlan:
    """Compute the full deploy plan by comparing files on disk against stored state.

    Each file is classified as:
      CREATE  — no state entry exists (never deployed)
      UPDATE  — state exists but content hash has changed
      NO_OP   — state exists and hash is unchanged

    If archive_orphans is True, files tracked in state but absent from disk are
    added as ARCHIVE actions.
    """
    plan = DeployPlan()

    cwd = Path.cwd()

    for filepath in sorted(files):
        try:
            rel_path = str(filepath.relative_to(cwd))
        except ValueError:
            rel_path = str(filepath)

        current_hash = state.compute_hash(filepath)
        entry = state.get_page(rel_path)
        title = _derive_title(filepath)

        if entry is None:
            plan.page_actions.append(
                PageAction(
                    filepath=filepath,
                    rel_path=rel_path,
                    action="CREATE",
                    title=title,
                    current_hash=current_hash,
                )
            )
        elif entry["content_hash"] != current_hash:
            plan.page_actions.append(
                PageAction(
                    filepath=filepath,
                    rel_path=rel_path,
                    action="UPDATE",
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
                    action="NO_OP",
                    title=title,
                    current_hash=current_hash,
                    stored_hash=entry["content_hash"],
                    page_id=entry["page_id"],
                )
            )

    if archive_orphans:
        for rel_path in state.find_orphans(files, docs_root):
            entry = state.get_page(rel_path)
            if entry:
                plan.orphan_actions.append(
                    OrphanAction(
                        rel_path=rel_path,
                        page_id=entry["page_id"],
                        title=entry["title"],
                    )
                )

    return plan
