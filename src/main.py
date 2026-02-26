"""Confluence Markdown Deployer - CLI Entry Point."""

import argparse
import os
import sys
from pathlib import Path

from config import load_config, merge_config_with_args
from deploy import ConfluenceAPI, archive_page, deploy_page, deploy_tree, ensure_page_hierarchy
from deploy.frontmatter import parse_frontmatter
from plan import compute_plan
from state import StateManager


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deploy markdown to Confluence Cloud")

    # Config file
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to ccfm.yaml config file (default: ccfm.yaml if present)",
    )

    # Confluence credentials
    parser.add_argument("--domain", default=None, help="Confluence domain")
    parser.add_argument("--email", default=None, help="User email")
    parser.add_argument(
        "--token",
        default=os.environ.get("CONFLUENCE_TOKEN"),
        help="API token (or set CONFLUENCE_TOKEN env var)",
    )
    parser.add_argument("--space", default=None, help="Space key")

    # Deployment targets
    parser.add_argument("--file", type=Path, help="Single markdown file to deploy")
    parser.add_argument("--directory", type=Path, help="Directory to deploy (recursive)")
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=None,
        help="Root documentation directory (default: docs)",
    )
    parser.add_argument("--git-repo-url", default="", help="Git repo URL for CI banner")

    # Behaviour flags
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Write ADF to .adf.json files and skip deployment",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Show what would be deployed without making any changes",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Only deploy files whose content has changed since last deploy",
    )
    parser.add_argument(
        "--archive-orphans",
        action="store_true",
        help="Archive Confluence pages for markdown files that no longer exist on disk",
    )

    # State file
    parser.add_argument(
        "--state",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to state file (default: .ccfm-state.json)",
    )

    return parser


def main():
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 1. Resolve and merge config file
    # ------------------------------------------------------------------
    config_path = args.config or Path("ccfm.yaml")
    if config_path.exists():
        try:
            config = load_config(config_path)
            args = merge_config_with_args(config, args)
        except Exception as e:
            print(f"Error loading config file '{config_path}': {e}")
            sys.exit(1)

    # Apply defaults that depend on config resolution
    if args.docs_root is None:
        args.docs_root = Path("docs")
    if args.state is None:
        args.state = Path(".ccfm-state.json")

    # ------------------------------------------------------------------
    # 2. Validate required credentials (not needed for --plan or --dump)
    # ------------------------------------------------------------------
    if not args.plan and not args.dump:
        missing = [f"--{f}" for f in ("domain", "email", "space") if not getattr(args, f, None)]
        if not args.token:
            missing.append("--token (or CONFLUENCE_TOKEN env var)")
        if missing:
            parser.error(f"Missing required arguments: {', '.join(missing)}")
    else:
        # plan/dump still need domain/space for context messages, but won't call API
        pass

    # ------------------------------------------------------------------
    # 3. Initialise state
    # ------------------------------------------------------------------
    state = StateManager(args.state)
    state.load()

    # ------------------------------------------------------------------
    # 4. Resolve target files
    # ------------------------------------------------------------------
    if args.file:
        target_files = [args.file]
    elif args.directory:
        all_md = sorted(args.directory.rglob("*.md"))
        target_files = [f for f in all_md if f.name != ".page_content.md"]
    else:
        print("Error: Specify either --file or --directory")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 5. Plan mode — show diff and exit
    # ------------------------------------------------------------------
    if args.plan:
        plan = compute_plan(
            state=state,
            files=target_files,
            docs_root=args.docs_root,
            archive_orphans=args.archive_orphans,
        )
        plan.print_summary()
        sys.exit(2 if plan.has_changes() else 0)

    # ------------------------------------------------------------------
    # 6. Changed-only filter
    # ------------------------------------------------------------------
    if args.changed_only:
        target_files = [f for f in target_files if state.has_changed(_rel_path(f), f)]
        print(f"ℹ️  --changed-only: {len(target_files)} file(s) with changes")

    # ------------------------------------------------------------------
    # 7. Dump mode — write ADF locally, no API calls
    # ------------------------------------------------------------------
    if args.dump:
        print("🔍 Dump mode — ADF will be written to .adf.json files, no deployment")
        if args.file:
            deploy_page(None, None, None, args.file, args.git_repo_url, dump=True)
        elif args.directory:
            deploy_tree(None, None, args.directory, args.docs_root, args.git_repo_url, dump=True)
        return

    # ------------------------------------------------------------------
    # 8. Live deployment
    # ------------------------------------------------------------------
    print(f"🔍 Looking up space: {args.space}")
    api = ConfluenceAPI(args.domain, args.email, args.token)
    space_id = api.get_space_id(args.space)
    print(f"   Space ID: {space_id}")

    if args.file:
        parent_id = ensure_page_hierarchy(
            api, space_id, args.file, args.docs_root, args.git_repo_url
        )
        page_id = deploy_page(api, space_id, parent_id, args.file, args.git_repo_url)
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

    elif args.directory:
        results = deploy_tree(api, space_id, args.directory, args.docs_root, args.git_repo_url)
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

    # ------------------------------------------------------------------
    # 9. Archive orphaned pages
    # ------------------------------------------------------------------
    if args.archive_orphans:
        orphans = state.find_orphans(target_files, args.docs_root)
        if orphans:
            print(f"\n🗄️  Archiving {len(orphans)} orphaned page(s)...")
            for rel_path in orphans:
                entry = state.get_page(rel_path)
                if entry:
                    success = archive_page(api, entry["page_id"], entry["title"])
                    if success:
                        state.remove_page(rel_path)
                        state.save()
        else:
            print("\nℹ️  No orphaned pages found.")

    print("\n✨ Deployment complete!")


if __name__ == "__main__":  # pragma: no cover
    main()
