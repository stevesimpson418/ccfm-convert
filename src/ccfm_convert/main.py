"""Confluence Markdown Deployer - CLI Entry Point."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from ccfm_convert.adf.converter import convert
from ccfm_convert.config import load_config, merge_config_with_args
from ccfm_convert.deploy import (
    ConfluenceAPI,
    add_ci_banner,
    deploy_tree,
    destroy_pages,
    ensure_page_hierarchy,
)
from ccfm_convert.deploy.dependencies import build_dependency_graph
from ccfm_convert.deploy.frontmatter import parse_frontmatter
from ccfm_convert.plan import compute_plan
from ccfm_convert.state import (
    ContentPropertyBackend,
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
    """Derive the page title from frontmatter, or fall back to the filename stem.
    For .page_content.md files, falls back to the parent directory name."""
    try:
        content = filepath.read_text(encoding="utf-8")
        metadata, _ = parse_frontmatter(content)
        if metadata.get("title"):
            return metadata["title"]
    except OSError:
        pass
    if filepath.name == ".page_content.md":
        return filepath.parent.name
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
    parser.add_argument(
        "--domain",
        default=os.environ.get("CONFLUENCE_DOMAIN"),
        help="Confluence domain (or set CONFLUENCE_DOMAIN env var)",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("CONFLUENCE_EMAIL"),
        help="User email (or set CONFLUENCE_EMAIL env var)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("CONFLUENCE_TOKEN"),
        help="API token (or set CONFLUENCE_TOKEN env var)",
    )
    parser.add_argument("--space", default=None, help="Space key")


def _add_target_args(parser: argparse.ArgumentParser) -> None:
    """Add target args shared by plan and apply."""
    parser.add_argument("--git-repo-url", default=None, help="Git repo URL for CI banner")
    parser.add_argument(
        "--ci-banner",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Enable/disable the CI banner globally. Use --no-ci-banner to disable "
            "across all pages. Overridden by per-page ci_banner in frontmatter. "
            "Defaults to True when neither CLI nor ccfm.yaml sets it."
        ),
    )


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
    plan_parser.add_argument(
        "--debug-file",
        type=Path,
        metavar="PATH",
        help="Convert a single file to ADF JSON and print to stdout (no API calls)",
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
    _normalize_domain(args)
    return args


def _normalize_domain(args):
    """Strip protocol prefix and trailing slashes from the domain.

    Users commonly provide "https://company.atlassian.net" when only the
    hostname is expected. Without this normalization the requests library
    tries to resolve "https" as a hostname and raises an opaque error.
    """
    if args.domain:
        domain = args.domain
        if domain.lower().startswith(("https://", "http://")):
            domain = domain.split("://", 1)[1]
        domain = domain.rstrip("/")
        args.domain = domain.split("/", 1)[0]


def _require_credentials(args, parser):
    """Validate that credentials are set. Exits on missing values."""
    label_map = {
        "domain": "--domain (or CONFLUENCE_DOMAIN env var)",
        "email": "--email (or CONFLUENCE_EMAIL env var)",
        "space": "--space",
    }
    missing = [label_map[f] for f in ("domain", "email", "space") if not getattr(args, f, None)]
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
        print("Error: CCFM has not been initialized in this space. Run `ccfm init` first.")
        sys.exit(1)
    page_id = api.find_child_page_by_title(container_id, MANAGEMENT_PAGE_TITLE)
    if page_id is None:
        print("Error: CCFM has not been initialized in this space. Run `ccfm init` first.")
        sys.exit(1)
    return page_id


def _resolve_target_files(args):
    """Resolve target files from docs_root.

    All deployments target the full docs_root directory. The docs_root must
    be set via docs_root in ccfm.yaml.

    Returns:
        Tuple of (target_files, container_files) where target_files are the
        regular markdown files to deploy and container_files are the
        ``.page_content.md`` files used for directory container pages.
    """
    docs_root = getattr(args, "docs_root", None)
    if not docs_root:
        print(
            "Error: No docs_root configured. Set docs_root in ccfm.yaml.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not docs_root.exists():
        print(f"Error: docs_root not found: {docs_root}", file=sys.stderr)
        sys.exit(1)
    if not docs_root.is_dir():
        print(f"Error: docs_root is not a directory: {docs_root}", file=sys.stderr)
        sys.exit(1)
    all_md = sorted(docs_root.rglob("*.md"))
    target_files = [f for f in all_md if f.name != ".page_content.md"]
    container_files = [f for f in all_md if f.name == ".page_content.md"]
    return target_files, container_files


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

    # --debug-file: convert a single file to ADF JSON and print to stdout
    debug_file = getattr(args, "debug_file", None)
    if debug_file:
        if not debug_file.exists():
            parser.error(f"File not found: {debug_file}")
        content = debug_file.read_text(encoding="utf-8")
        metadata, markdown = parse_frontmatter(content)
        body = convert(markdown)
        git_repo_url = getattr(args, "git_repo_url", None) or ""
        file_url = f"{git_repo_url}/{debug_file}" if git_repo_url else ""
        global_ci_banner_text = getattr(args, "ci_banner_text", None)
        global_ci_banner = getattr(args, "ci_banner", None)
        body = add_ci_banner(
            body,
            metadata,
            file_url,
            global_ci_banner_text=global_ci_banner_text,
            global_ci_banner=global_ci_banner,
        )
        print(json.dumps(body, indent=2))
        return

    target_files, container_files = _resolve_target_files(args)

    # Build dependency graph for ordering
    dep_graph = None
    if len(target_files) > 1:
        dep_graph = build_dependency_graph(target_files, container_files)

    _require_credentials(args, parser)
    api = _create_api(args)
    print(f"Looking up space: {args.space}")
    space_id = api.get_space_id(args.space)
    print(f"   Space ID: {space_id}")

    mgmt_page_id = _find_management_page(api, space_id)
    backend = ContentPropertyBackend(api, mgmt_page_id)
    state = StateManager(backend)
    state.load()

    force = getattr(args, "force", False)
    plan = compute_plan(
        state=state,
        files=target_files,
        docs_root=args.docs_root,
        force=force,
        page_content_files=container_files,
    )
    plan.dependency_graph = dep_graph
    plan.print_summary()

    if getattr(args, "plan_exit_code", False):
        sys.exit(2 if plan.has_changes() else 0)


def _handle_apply(args, parser):
    """Handle the 'apply' subcommand."""

    target_files, container_files = _resolve_target_files(args)

    # Build dependency graph for ordering
    dep_graph = None
    if len(target_files) > 1:
        dep_graph = build_dependency_graph(target_files, container_files)

    _require_credentials(args, parser)
    api = _create_api(args)
    print(f"Looking up space: {args.space}")
    space_id = api.get_space_id(args.space)
    print(f"   Space ID: {space_id}")

    mgmt_page_id = _find_management_page(api, space_id)
    backend = ContentPropertyBackend(api, mgmt_page_id)
    state = StateManager(backend)
    state.load()

    # Compute plan
    force = getattr(args, "force", False)
    plan = compute_plan(
        state=state,
        files=target_files,
        docs_root=args.docs_root,
        force=force,
        page_content_files=container_files,
    )
    plan.dependency_graph = dep_graph
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

    git_repo_url = getattr(args, "git_repo_url", None) or ""
    ci_banner_text = getattr(args, "ci_banner_text", None)
    ci_banner = getattr(args, "ci_banner", None)
    try:
        # Separate regular files from .page_content.md files
        regular_actionable = [
            a
            for a in plan.page_actions
            if a.action != "no-op" and a.filepath.name != ".page_content.md"
        ]
        pc_actionable = [
            a
            for a in plan.page_actions
            if a.action != "no-op" and a.filepath.name == ".page_content.md"
        ]

        all_hierarchy_pages: list[tuple[str, str, str]] = []

        # Compute set of container directories whose .page_content.md actually changed
        changed_containers = (
            {str(a.filepath.parent.relative_to(args.docs_root)) for a in pc_actionable}
            if pc_actionable
            else set()
        )

        # Execute regular adds/changes via deploy_tree
        if regular_actionable:
            actionable_files = [a.filepath for a in regular_actionable]

            # Reorder by dependency graph if available
            if dep_graph:
                ordered_set = set(actionable_files)
                actionable_files = [f for f in dep_graph.order if f in ordered_set]

            results, hierarchy_pages = deploy_tree(
                api,
                space_id,
                args.docs_root,
                git_repo_url,
                files=actionable_files,
                ci_banner_text=ci_banner_text,
                ci_banner=ci_banner,
                changed_containers=changed_containers,
            )
            all_hierarchy_pages.extend(hierarchy_pages)
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

        # Deploy .page_content.md changes not already covered by deploy_tree
        if pc_actionable:
            processed_dirs = {hp[0] for hp in all_hierarchy_pages}
            for action in pc_actionable:
                pc_dir_rel = _rel_path(action.filepath.parent)
                if pc_dir_rel not in processed_dirs:
                    _, h_pages = ensure_page_hierarchy(
                        api,
                        space_id,
                        action.filepath,
                        args.docs_root,
                        git_repo_url,
                        ci_banner_text=ci_banner_text,
                        ci_banner=ci_banner,
                        changed_containers=changed_containers,
                    )
                    for hp in h_pages:
                        if hp[0] not in processed_dirs:
                            all_hierarchy_pages.append(hp)
                            processed_dirs.add(hp[0])

        # Store state for all hierarchy pages (with actual hash when .page_content.md exists)
        for h_rel_path, h_page_id, h_title in all_hierarchy_pages:
            pc_file = Path(h_rel_path) / ".page_content.md"
            content_hash = state.compute_hash(pc_file) if pc_file.exists() else ""
            state.set_page(
                rel_path=h_rel_path,
                page_id=h_page_id,
                title=h_title,
                space_key=args.space,
                space_id=space_id,
                content_hash=content_hash,
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
    backend = ContentPropertyBackend(api, mgmt_page_id)
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
            # Re-load *inside* the lock so the backend's version cache reflects
            # the current state of every property at the moment we're about to
            # write. ``state push`` is unique among the state-mutating commands
            # in writing arbitrary user-supplied data — apply and ``state rm``
            # both use the cache-skip-when-unchanged path which naturally
            # preserves concurrent changes to entries we don't touch and
            # surfaces real conflicts as 409s. ``state push``, by contrast,
            # asks the backend to make the remote look exactly like the input
            # file, so a stale cache would cause spurious 409s on every
            # entry that any concurrent writer touched between the pre-lock
            # ``state.load()`` above and the lock acquisition.
            backend.load()
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
    elif args.command == "state":
        _handle_state(args, parser)
    elif args.command == "lock":
        _handle_lock(args, parser)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
