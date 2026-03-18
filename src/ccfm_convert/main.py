"""Confluence Markdown Deployer - CLI Entry Point."""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ccfm_convert.config import load_config, merge_config_with_args
from ccfm_convert.deploy import (
    ConfluenceAPI,
    deploy_page,
    deploy_tree,
    destroy_pages,
    dump_page,
    dump_tree,
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


def _add_target_args(parser: argparse.ArgumentParser) -> None:
    """Add --file, --directory, --docs-root, --git-repo-url shared by plan and apply."""
    parser.add_argument("--file", type=Path, help="Single markdown file to target")
    parser.add_argument(
        "--directory",
        type=Path,
        help="Directory to target, recursive (default: docs_root from ccfm.yaml)",
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=None,
        help="Root documentation directory (default: docs)",
    )
    parser.add_argument("--git-repo-url", default="", help="Git repo URL for CI banner")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deploy markdown to Confluence Cloud")
    _add_global_args(parser)

    subparsers = parser.add_subparsers(dest="command")

    # -- init ------------------------------------------------------------
    subparsers.add_parser("init", help="Initialize remote state infrastructure in the space")

    # -- plan ------------------------------------------------------------
    plan_parser = subparsers.add_parser("plan", help="Show what ccfm would do without applying")
    _add_target_args(plan_parser)
    plan_parser.add_argument(
        "--plan-exit-code",
        action="store_true",
        help="Exit 2 when changes are pending (useful for CI gating)",
    )
    plan_parser.add_argument(
        "--force",
        action="store_true",
        help="Treat all files as new (force re-deploy on next apply)",
    )

    # -- apply -----------------------------------------------------------
    apply_parser = subparsers.add_parser("apply", help="Apply changes to Confluence")
    _add_target_args(apply_parser)
    apply_parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip interactive confirmation prompt (for CI/CD)",
    )
    apply_parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-deploy of all files regardless of state",
    )
    apply_parser.add_argument(
        "--lock-id",
        default=None,
        help="Lock identifier for CI traceability (default: user@hostname)",
    )

    # -- dump ------------------------------------------------------------
    dump_parser = subparsers.add_parser(
        "dump", help="Convert markdown to ADF JSON files for inspection (no API calls)"
    )
    _add_target_args(dump_parser)
    dump_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for .adf.json files (default: .ccfm/dumps/<timestamp>/)",
    )

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


def _resolve_directory(args):
    """Return the effective target directory from --directory or docs_root fallback.

    Returns --directory if set, otherwise falls back to docs_root when the
    _docs_root_from_config flag indicates it came from ccfm.yaml (user intent).
    Also sets args.directory as a side effect so downstream dispatch logic
    (e.g., _handle_apply's file-vs-directory branching) sees a consistent value.
    """
    directory = getattr(args, "directory", None)
    if not directory and getattr(args, "_docs_root_from_config", False):
        docs_root = getattr(args, "docs_root", None)
        if docs_root:
            directory = docs_root
            args.directory = directory
    return directory


def _resolve_target_files(args):
    """Resolve target files from --file, --directory, or docs_root fallback.

    Precedence order:
      1. --file (explicit single file)
      2. --directory (explicit directory)
      3. docs_root from config when _docs_root_from_config flag is set

    The flag distinguishes a docs_root that came from ccfm.yaml (user intent
    to deploy that directory) from the handler's internal default of Path("docs")
    which is only used for hierarchy calculations, not as a deploy target.
    """
    if hasattr(args, "file") and args.file:
        if not args.file.exists():
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        return [args.file]

    directory = _resolve_directory(args)

    if directory:
        if not directory.exists():
            print(f"Error: Directory not found: {directory}", file=sys.stderr)
            sys.exit(1)
        all_md = sorted(directory.rglob("*.md"))
        return [f for f in all_md if f.name != ".page_content.md"]
    else:
        print("Error: Specify either --file or --directory (or set docs_root in ccfm.yaml)")
        sys.exit(1)


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
    print("\nAll files inside your docs_root directory will be managed by ccfm.")
    print("Removing files or folders will result in destroy operations on the next apply.")


def _handle_plan(args, parser):
    """Handle the 'plan' subcommand."""
    if not hasattr(args, "docs_root") or args.docs_root is None:
        args.docs_root = Path("docs")

    target_files = _resolve_target_files(args)

    _require_credentials(args, parser)
    api = _create_api(args)
    print(f"Looking up space: {args.space}")
    space_id = api.get_space_id(args.space)
    print(f"   Space ID: {space_id}")

    mgmt_page_id = _find_management_page(api, space_id)
    backend = ConfluenceBackend(api, mgmt_page_id)
    state = StateManager(backend)
    state.load()

    force = getattr(args, "force", False)
    plan = compute_plan(state=state, files=target_files, docs_root=args.docs_root, force=force)
    plan.print_summary()

    if getattr(args, "plan_exit_code", False):
        sys.exit(2 if plan.has_changes() else 0)


def _handle_dump(args, parser):
    """Handle the 'dump' subcommand."""
    if not hasattr(args, "docs_root") or args.docs_root is None:
        args.docs_root = Path("docs")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or Path(".ccfm") / "dumps" / f"{timestamp}_{uuid.uuid4().hex[:8]}"
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error: Cannot create output directory '{output_dir}': {e}", file=sys.stderr)
        sys.exit(1)

    git_repo_url = getattr(args, "git_repo_url", "")

    if hasattr(args, "file") and args.file:
        if not args.file.exists():
            parser.error(f"File not found: {args.file}")
        dump_page(args.file, output_dir, git_repo_url)
    else:
        directory = _resolve_directory(args)
        if directory:
            if not directory.exists():
                parser.error(f"Directory not found: {directory}")
            dump_tree(directory, args.docs_root, output_dir, git_repo_url)
        else:
            print("Error: Specify either --file or --directory (or set docs_root in ccfm.yaml)")
            sys.exit(1)

    print(f"\nDump complete! ADF files written to: {output_dir}")


def _handle_apply(args, parser):
    """Handle the 'apply' subcommand."""
    if not hasattr(args, "docs_root") or args.docs_root is None:
        args.docs_root = Path("docs")

    target_files = _resolve_target_files(args)

    _require_credentials(args, parser)
    api = _create_api(args)
    print(f"Looking up space: {args.space}")
    space_id = api.get_space_id(args.space)
    print(f"   Space ID: {space_id}")

    mgmt_page_id = _find_management_page(api, space_id)
    backend = ConfluenceBackend(api, mgmt_page_id)
    state = StateManager(backend)
    state.load()

    # Compute plan
    force = getattr(args, "force", False)
    plan = compute_plan(state=state, files=target_files, docs_root=args.docs_root, force=force)
    plan.print_summary()

    if not plan.has_changes():
        print("No changes to apply.")
        return

    # Confirmation prompt
    auto_approve = getattr(args, "auto_approve", False)
    if not auto_approve:
        if not sys.stdin.isatty():
            print(
                "Error: apply requires confirmation. Use --auto-approve for non-interactive mode."
            )
            sys.exit(1)
        answer = input("\nDo you want to apply these changes? Only 'yes' will be accepted: ")
        if answer.strip().lower() != "yes":
            print("Apply cancelled.")
            return

    # Acquire lock
    lock_mgr = LockManager(api, mgmt_page_id)
    lock_id = getattr(args, "lock_id", None)
    try:
        lock_mgr.acquire(operation="apply", lock_id=lock_id)
    except LockError as e:
        print(f"Error: {e}")
        sys.exit(1)

    git_repo_url = getattr(args, "git_repo_url", "")
    try:
        # Execute adds/changes
        actionable = [a for a in plan.page_actions if a.action != "no-op"]
        if actionable:
            actionable_files = [a.filepath for a in actionable]
            if hasattr(args, "file") and args.file:
                target = actionable_files[0]
                parent_id, hierarchy_pages = ensure_page_hierarchy(
                    api, space_id, target, args.docs_root, git_repo_url
                )
                page_id = deploy_page(api, space_id, parent_id, target, git_repo_url)
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
                        rel_path=_rel_path(target),
                        page_id=page_id,
                        title=_derive_title(target),
                        space_key=args.space,
                        space_id=space_id,
                        content_hash=state.compute_hash(target),
                    )
            elif hasattr(args, "directory") and args.directory:
                results, hierarchy_pages = deploy_tree(
                    api,
                    space_id,
                    args.directory,
                    args.docs_root,
                    git_repo_url,
                    files=actionable_files,
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

        # Execute destroys
        if plan.destroy_actions:
            print(f"\nDestroying {len(plan.destroy_actions)} page(s)...")
            destroy_pages(api, state, plan.destroy_actions)

        state.save()
        print("\nApply complete!")
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
    elif args.command == "plan":
        _handle_plan(args, parser)
    elif args.command == "apply":
        _handle_apply(args, parser)
    elif args.command == "dump":
        _handle_dump(args, parser)
    elif args.command == "state":
        _handle_state(args, parser)
    elif args.command == "lock":
        _handle_lock(args, parser)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
