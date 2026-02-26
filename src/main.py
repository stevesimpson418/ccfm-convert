"""Confluence Markdown Deployer - CLI Entry Point."""

import argparse
import os
import sys
from pathlib import Path

from deploy import ConfluenceAPI, deploy_page, deploy_tree, ensure_page_hierarchy


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Deploy markdown to Confluence Cloud")
    parser.add_argument("--domain", required=True, help="Confluence domain")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument(
        "--token",
        default=os.environ.get("CONFLUENCE_TOKEN"),
        help="API token (or set CONFLUENCE_TOKEN env var)",
    )
    parser.add_argument("--space", required=True, help="Space key")
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path("docs"),
        help="Root documentation directory (default: docs)",
    )
    parser.add_argument("--file", type=Path, help="Single markdown file to deploy")
    parser.add_argument("--directory", type=Path, help="Directory to deploy (recursive)")
    parser.add_argument("--git-repo-url", default="", help="Git repo URL for CI banner")
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Write ADF to .adf.json files and skip deployment",
    )

    args = parser.parse_args()

    if not args.token:
        parser.error("--token is required (or set CONFLUENCE_TOKEN env var)")

    # Create API instance
    api = ConfluenceAPI(args.domain, args.email, args.token)

    if args.dump:
        print("🔍 Dump mode — ADF will be written to .adf.json files, no deployment")
        space_id = None
    else:
        print(f"🔍 Looking up space: {args.space}")
        space_id = api.get_space_id(args.space)
        print(f"   Space ID: {space_id}")

    if args.file:
        # Single file deployment with automatic page hierarchy
        if not args.dump:
            parent_id = ensure_page_hierarchy(
                api, space_id, args.file, args.docs_root, args.git_repo_url
            )
        else:
            parent_id = None

        deploy_page(api, space_id, parent_id, args.file, args.git_repo_url, dump=args.dump)

    elif args.directory:
        # Tree deployment - deploy entire directory structure
        deploy_tree(
            api, space_id, args.directory, args.docs_root, args.git_repo_url, dump=args.dump
        )

    else:
        print("Error: Specify either --file or --directory")
        sys.exit(1)

    if not args.dump:
        print("\n✨ Deployment complete!")


if __name__ == "__main__":  # pragma: no cover
    main()
