"""Confluence Markdown Deployer - CLI Entry Point."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from ccfm_convert.config import load_config, merge_config_with_args
from ccfm_convert.deploy import (
    ConfluenceAPI,
    archive_page,
    deploy_page,
    deploy_tree,
    ensure_page_hierarchy,
)
from ccfm_convert.deploy.frontmatter import parse_frontmatter
from ccfm_convert.plan import compute_plan
from ccfm_convert.state import (
    ConfluenceBackend,
    LockError,
    LockManager,
    StateManager,
    init_remote_state,
)
from ccfm_convert.state.init import CONTAINER_PAGE_TITLE, MANAGEMENT_PAGE_TITLE


def _rel_path(filepath: Path) -> str:
    """Return filepath relative to cwd, or absolute string if not under cwd."""
    try:
        return str(filepath.relative_to(Path.cwd()))
    except ValueError:
        return str(filepath)


def _derive_title(filepath: Path) -> str:
    """Derive the page title from frontmatter, or fall back to the filename stem."""
    try:
        content = filepath.read_text(encoding="utf-8")
        metadata, _ = parse_frontmatter(content)
        if metadata.get("title"):
            return metadata["title"]
    except OSError:
        pass
    return filepath.stem.replace("-", " ").title()


def _add_global_args(parser: argparse.ArgumentParser) -> None:
    """Add global arguments shared across all subcommands."""
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to ccfm.yaml config file (default: ccfm.yaml if present)",
    )
    parser.add_argument("--domain", default=None, help="Confluence domain")
    parser.add_argument("--email", default=None, help="User email")
    parser.add_argument(
        "--token",
        default=os.environ.get("CONFLUENCE_TOKEN"),
        help="API token (or set CONFLUENCE_TOKEN env var)",
    )
    parser.add_argument("--space", default=None, help="Space key")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deploy markdown to Confluence Cloud")
    _add_global_args(parser)

    subparsers = parser.add_subparsers(dest="command")

    # -- deploy ----------------------------------------------------------
    deploy_parser = subparsers.add_parser("deploy", help="Deploy markdown to Confluence")
    deploy_parser.add_argument("--file", type=Path, help="Single markdown file to deploy")
    deploy_parser.add_argument("--directory", type=Path, help="Directory to deploy (recursive)")
    deploy_parser.add_argument(
        "--docs-root",
        type=Path,
        default=None,
        help="Root documentation directory (default: docs)",
    )
    deploy_parser.add_argument("--git-repo-url", default="", help="Git repo URL for CI banner")
    deploy_parser.add_argument(
        "--dump",
        action="store_true",
        help="Write ADF to .adf.json files and skip deployment",
    )
    deploy_parser.add_argument(
        "--plan",
        action="store_true",
        help="Show what would be deployed without making any changes",
    )
    deploy_parser.add_argument(
        "--plan-exit-code",
        action="store_true",
        help="With --plan, exit 2 when changes are pending (Terraform-style)",
    )
    deploy_parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Only deploy files whose content has changed since last deploy",
    )
    deploy_parser.add_argument(
        "--archive-orphans",
        action="store_true",
        help="Archive Confluence pages for markdown files that no longer exist on disk",
    )
    deploy_parser.add_argument(
        "--lock-id",
        default=None,
        help="Lock identifier for CI traceability (default: user@hostname)",
    )

    # -- init ------------------------------------------------------------
    subparsers.add_parser("init", help="Initialize remote state infrastructure in the space")

    # -- state -----------------------------------------------------------
    state_parser = subparsers.add_parser("state", help="Inspect or modify remote state")
    state_sub = state_parser.add_subparsers(dest="state_command")
    state_sub.add_parser("list", help="List all tracked pages")
    state_sub.add_parser("pull", help="Print remote state JSON to stdout")
    state_push = state_sub.add_parser("push", help="Overwrite remote state from a local file")
    state_push.add_argument("file", type=Path, help="Local JSON file to upload as new state")
    state_rm = state_sub.add_parser("rm", help="Remove a state entry by path")
    state_rm.add_argument("path", help="Relative path of the entry to remove")
    state_show = state_sub.add_parser("show", help="Show state entry for a specific path")
    state_show.add_argument("path", help="Relative path of the tracked page")

    # -- lock ------------------------------------------------------------
    lock_parser = subparsers.add_parser("lock", help="Manage the remote state lock")
    lock_sub = lock_parser.add_subparsers(dest="lock_command")
    lock_sub.add_parser("status", help="Show current lock status")
    lock_sub.add_parser("release", help="Force-release the remote lock")
    lock_acquire = lock_sub.add_parser("acquire", help="Manually acquire the remote lock")
    lock_acquire.add_argument("--lock-id", default=None, help="Lock identifier")
    lock_acquire.add_argument("--operation", default="manual", help="Operation label")

    return parser


def _resolve_config(args):
    """Merge config file values into args. Returns updated args."""
    config_path = args.config or Path("ccfm.yaml")
    if config_path.exists():
        try:
            config = load_config(config_path)
            args = merge_config_with_args(config, args)
        except Exception as e:
            print(f"Error loading config file '{config_path}': {e}")
            sys.exit(1)
    return args


def _require_credentials(args, parser):
    """Validate that credentials are set. Exits on missing values."""
    missing = [f"--{f}" for f in ("domain", "email", "space") if not getattr(args, f, None)]
    if not args.token:
        missing.append("--token (or CONFLUENCE_TOKEN env var)")
    if missing:
        parser.error(f"Missing required arguments: {', '.join(missing)}")


def _create_api(args):
    """Create and return a ConfluenceAPI instance."""
    return ConfluenceAPI(args.domain, args.email, args.token)


def _find_management_page(api, space_id):
    """Find the CCFM management page via the _ccfm container. Returns page_id or exits.

    Uses container → child lookup instead of label search so that orphaned
    management pages from failed cleanups are never returned.
    """
    container_id = api.find_page_by_title(space_id, CONTAINER_PAGE_TITLE)
    if container_id is None:
        print("Error: CCFM has not been initialized in this space. " "Run `ccfm init` first.")
        sys.exit(1)
    page_id = api.find_child_page_by_title(container_id, MANAGEMENT_PAGE_TITLE)
    if page_id is None:
        print("Error: CCFM has not been initialized in this space. " "Run `ccfm init` first.")
        sys.exit(1)
    return page_id


# ======================================================================
# Subcommand handlers
# ======================================================================


def _handle_init(args, parser):
    """Handle the 'init' subcommand."""
    _require_credentials(args, parser)
    api = _create_api(args)
    print(f"Looking up space: {args.space}")
    space_id = api.get_space_id(args.space)
    init_remote_state(api, args.space, space_id)
    print("\nInitialization complete!")


def _handle_deploy(args, parser):
    """Handle the 'deploy' subcommand."""
    # Apply deploy-specific defaults
    if not hasattr(args, "docs_root") or args.docs_root is None:
        args.docs_root = Path("docs")

    # Resolve target files
    if hasattr(args, "file") and args.file:
        target_files = [args.file]
    elif hasattr(args, "directory") and args.directory:
        all_md = sorted(args.directory.rglob("*.md"))
        target_files = [f for f in all_md if f.name != ".page_content.md"]
    else:
        print("Error: Specify either --file or --directory")
        sys.exit(1)

    # Snapshot all files before --changed-only filtering (for orphan detection)
    all_files = list(target_files)

    # --dump mode: no API, no state, no lock
    if hasattr(args, "dump") and args.dump:
        print("Dump mode — ADF will be written to .adf.json files, no deployment")
        git_repo_url = getattr(args, "git_repo_url", "")
        if hasattr(args, "file") and args.file:
            deploy_page(None, None, None, args.file, git_repo_url, dump=True)
        elif hasattr(args, "directory") and args.directory:
            deploy_tree(None, None, args.directory, args.docs_root, git_repo_url, dump=True)
        return

    # All non-dump paths need credentials and API
    _require_credentials(args, parser)
    api = _create_api(args)
    print(f"Looking up space: {args.space}")
    space_id = api.get_space_id(args.space)
    print(f"   Space ID: {space_id}")

    # Find management page for state + locking
    mgmt_page_id = _find_management_page(api, space_id)
    backend = ConfluenceBackend(api, mgmt_page_id)
    state = StateManager(backend)
    state.load()

    # --plan mode: read-only, no lock needed
    if hasattr(args, "plan") and args.plan:
        plan = compute_plan(
            state=state,
            files=target_files,
            docs_root=args.docs_root,
            archive_orphans=getattr(args, "archive_orphans", False),
        )
        plan.print_summary()
        if getattr(args, "plan_exit_code", False):
            sys.exit(2 if plan.has_changes() else 0)
        sys.exit(0)

    # --changed-only filter
    if getattr(args, "changed_only", False):
        target_files = [f for f in target_files if state.has_changed(_rel_path(f), f)]
        print(f"--changed-only: {len(target_files)} file(s) with changes")
        if not target_files:
            print("No changes to deploy.")
            return

    # Acquire lock for live deployment
    lock_mgr = LockManager(api, mgmt_page_id)
    lock_id = getattr(args, "lock_id", None)
    try:
        lock_mgr.acquire(operation="deploy", lock_id=lock_id)
    except LockError as e:
        print(f"Error: {e}")
        sys.exit(1)

    git_repo_url = getattr(args, "git_repo_url", "")
    try:
        # Live deployment
        if hasattr(args, "file") and args.file:
            parent_id, hierarchy_pages = ensure_page_hierarchy(
                api, space_id, args.file, args.docs_root, git_repo_url
            )
            page_id = deploy_page(api, space_id, parent_id, args.file, git_repo_url)
            for h_rel_path, h_page_id, h_title in hierarchy_pages:
                state.set_page(
                    rel_path=h_rel_path,
                    page_id=h_page_id,
                    title=h_title,
                    space_key=args.space,
                    space_id=space_id,
                    content_hash="",
                )
            if page_id:
                state.set_page(
                    rel_path=_rel_path(args.file),
                    page_id=page_id,
                    title=_derive_title(args.file),
                    space_key=args.space,
                    space_id=space_id,
                    content_hash=state.compute_hash(args.file),
                )
            state.save()

        elif hasattr(args, "directory") and args.directory:
            results, hierarchy_pages = deploy_tree(
                api,
                space_id,
                args.directory,
                args.docs_root,
                git_repo_url,
                files=target_files if getattr(args, "changed_only", False) else None,
            )
            for h_rel_path, h_page_id, h_title in hierarchy_pages:
                state.set_page(
                    rel_path=h_rel_path,
                    page_id=h_page_id,
                    title=h_title,
                    space_key=args.space,
                    space_id=space_id,
                    content_hash="",
                )
            for filepath, page_id in results:
                if page_id:
                    state.set_page(
                        rel_path=_rel_path(filepath),
                        page_id=page_id,
                        title=_derive_title(filepath),
                        space_key=args.space,
                        space_id=space_id,
                        content_hash=state.compute_hash(filepath),
                    )
            state.save()

        # Archive orphaned pages
        if getattr(args, "archive_orphans", False):
            orphans = state.find_orphans(all_files, args.docs_root)
            if orphans:
                print(f"\nArchiving {len(orphans)} orphaned page(s)...")
                archived_any = False
                for rel_path in orphans:
                    entry = state.get_page(rel_path)
                    if entry:
                        success = archive_page(api, entry["page_id"], entry["title"])
                        if success:
                            state.remove_page(rel_path)
                            archived_any = True
                if archived_any:
                    # If save() throws here, in-memory state has orphans removed but
                    # remote state has not been updated. Re-run --archive-orphans to
                    # retry. The lock will be released normally by the outer finally.
                    state.save()
            else:
                print("\nNo orphaned pages found.")

        print("\nDeployment complete!")
    finally:
        lock_mgr.release()


def _handle_state(args, parser):
    """Handle the 'state' subcommand."""
    if not hasattr(args, "state_command") or args.state_command is None:
        print("Error: Specify a state subcommand: list, pull, push, rm, show")
        sys.exit(1)

    _require_credentials(args, parser)
    api = _create_api(args)
    space_id = api.get_space_id(args.space)
    mgmt_page_id = _find_management_page(api, space_id)
    backend = ConfluenceBackend(api, mgmt_page_id)
    state = StateManager(backend)
    state.load()

    if args.state_command == "list":
        pages = state.all_pages
        if not pages:
            print("No pages tracked in state.")
            return
        print(f"Tracked pages ({len(pages)}):\n")
        for rel_path, entry in sorted(pages.items()):
            print(f"  {rel_path}")
            print(f"    page_id: {entry['page_id']}")
            print(f"    title:   {entry['title']}")
            print(f"    deployed: {entry.get('deployed_at', 'unknown')}")
            print()

    elif args.state_command == "pull":
        print(json.dumps(state.raw_state, indent=2, sort_keys=True))

    elif args.state_command == "push":
        try:
            raw = args.file.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Error reading '{args.file}': {e}")
            sys.exit(1)
        if (
            not isinstance(data, dict)
            or "version" not in data
            or "pages" not in data
            or not isinstance(data["pages"], dict)
        ):
            print("Error: invalid state file — must have 'version' key and 'pages' dict.")
            sys.exit(1)
        for path_key, entry in data["pages"].items():
            pid = entry.get("page_id") if isinstance(entry, dict) else None
            if not isinstance(pid, str) or not re.match(r"^[1-9]\d*$", pid):
                display_key = "".join(c for c in path_key[:200] if c.isprintable())
                print(
                    f"Error: invalid state file — entry '{display_key}' has missing or "
                    "invalid 'page_id' (must be a quoted positive integer string, "
                    'e.g. "12345", with no leading zeros).'
                )
                sys.exit(1)
        lock_mgr = LockManager(api, mgmt_page_id)
        try:
            lock_mgr.acquire(operation="state-push")
        except LockError as e:
            print(f"Error: cannot push state while locked: {e}")
            sys.exit(1)
        try:
            print("Warning: this overwrites remote state. Use with caution.")
            backend.save(data)
            print(f"Remote state updated from '{args.file}'.")
        finally:
            lock_mgr.release()

    elif args.state_command == "rm":
        rel_path = args.path
        entry = state.get_page(rel_path)
        if entry is None:
            print(f"Error: '{rel_path}' is not tracked in state.")
            sys.exit(1)
        lock_mgr = LockManager(api, mgmt_page_id)
        try:
            lock_mgr.acquire(operation="state-rm")
        except LockError as e:
            print(f"Error: cannot remove state entry while locked: {e}")
            sys.exit(1)
        try:
            state.remove_page(rel_path)
            state.save()
            print(f"Removed '{rel_path}' from state.")
        finally:
            lock_mgr.release()

    elif args.state_command == "show":
        rel_path = args.path
        entry = state.get_page(rel_path)
        if entry is None:
            print(f"Error: '{rel_path}' is not tracked in state.")
            sys.exit(1)
        print(json.dumps(entry, indent=2, sort_keys=True))


def _handle_lock(args, parser):
    """Handle the 'lock' subcommand."""
    if not hasattr(args, "lock_command") or args.lock_command is None:
        print("Error: Specify a lock subcommand: acquire, status, release")
        sys.exit(1)

    _require_credentials(args, parser)
    api = _create_api(args)
    space_id = api.get_space_id(args.space)
    mgmt_page_id = _find_management_page(api, space_id)
    lock_mgr = LockManager(api, mgmt_page_id)

    if args.lock_command == "acquire":
        try:
            lock_id = getattr(args, "lock_id", None)
            operation = getattr(args, "operation", "manual")
            lock_mgr.acquire(operation=operation, lock_id=lock_id)
            info = lock_mgr.status()
            print(f"Lock acquired by {info.owner} (operation: {info.operation})")
        except LockError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.lock_command == "status":
        info = lock_mgr.status()
        if not info.locked:
            print("State is not locked.")
        else:
            print("State is locked:")
            print(f"  Owner:     {info.owner}")
            if info.lock_id:
                print(f"  Lock ID:   {info.lock_id}")
            print(f"  Since:     {info.locked_at}")
            print(f"  Operation: {info.operation}")

    elif args.lock_command == "release":
        lock_mgr.force_release()
        print("Lock released.")


def main():
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    # Resolve config file
    args = _resolve_config(args)

    # Route to subcommand handler
    if args.command == "init":
        _handle_init(args, parser)
    elif args.command == "deploy":
        _handle_deploy(args, parser)
    elif args.command == "state":
        _handle_state(args, parser)
    elif args.command == "lock":
        _handle_lock(args, parser)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
