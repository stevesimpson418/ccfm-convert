"""Deployment Orchestration."""

import json
from pathlib import Path

from adf import convert

from .frontmatter import parse_frontmatter
from .transforms import add_ci_banner, resolve_page_links


def ensure_page_hierarchy(api, space_id, filepath, docs_root, git_repo_url=""):
    """
    Ensure all parent pages exist for a file path.

    Creates container pages for each directory in the path. If a .page_content.md
    file exists in the directory, treats it as a full page with frontmatter.
    Otherwise creates a placeholder.

    Args:
        api: ConfluenceAPI instance
        space_id: Target space ID
        filepath: Path to the file (e.g., Path("docs/Team/Engineering/api-guide.md"))
        docs_root: Root documentation directory (e.g., Path("docs"))
        git_repo_url: Git repo URL for CI banner

    Returns:
        Parent page ID for the file (the immediate parent page's ID)
    """
    # Get relative path from docs root
    try:
        rel_path = filepath.relative_to(docs_root)
    except ValueError:
        # File is not under docs_root
        return None

    # Get directory path (everything except the filename)
    dir_path = rel_path.parent

    # If file is directly in docs root, no parent needed
    if str(dir_path) == ".":
        return None

    # Create each directory as a page in the hierarchy
    parts = dir_path.parts
    current_parent_id = None

    for i, dir_name in enumerate(parts):
        # Build path to this directory
        current_dir = docs_root / Path(*parts[: i + 1])
        page_content_file = current_dir / ".page_content.md"

        # Determine title and body
        if page_content_file.exists():
            print(f"   📄 Ensuring page: {dir_name} (with .page_content.md)")
            # Treat like a regular page
            content = page_content_file.read_text()
            metadata, markdown = parse_frontmatter(content)

            # Get title from frontmatter or default to directory name
            title = metadata.get("title", dir_name)
            page_status = metadata.get("page_status", "current")

            # Convert markdown to ADF
            body = convert(markdown)

            # Add CI banner if enabled
            if metadata.get("ci_banner", True):
                file_git_url = f"{git_repo_url}/{page_content_file}" if git_repo_url else ""
                custom_banner_text = metadata.get("ci_banner_text")
                body = add_ci_banner(
                    body, file_git_url, banner_text=custom_banner_text, metadata=metadata
                )

            labels = metadata.get("labels", [])
            author = metadata.get("author")
        else:
            print(f"   📄 Ensuring page: {dir_name} (placeholder)")
            # Create placeholder
            title = dir_name
            page_status = "current"
            placeholder_markdown = f"# {dir_name}\n\nContainer page for {dir_name} content."
            body = convert(placeholder_markdown)
            labels = []
            author = None

        # Check if page already exists
        page_id = api.find_page_by_title(space_id, title)

        if page_id:
            print(f"   ✓ Page '{title}' exists (ID: {page_id})")
            # If .page_content.md exists, update the page with new content
            if page_content_file.exists():
                print(f"   ♻️  Updating page '{title}' with .page_content.md content")
                api.update_page(page_id, title, body, status=page_status)

                # Update labels
                if labels or author:
                    if author:
                        author_label = f"author-{author.lower().replace(' ', '-')}"
                        labels.append(author_label)
                    api.add_labels(page_id, labels)

            current_parent_id = page_id
        else:
            # Create the container page
            print(f"   ✨ Creating page: {title}")
            current_parent_id = api.create_page(
                space_id, current_parent_id, title, body, status=page_status
            )

            # Add labels
            if labels or author:
                if author:
                    author_label = f"author-{author.lower().replace(' ', '-')}"
                    labels.append(author_label)
                api.add_labels(current_parent_id, labels)

    return current_parent_id


def deploy_tree(api, space_id, root_path, docs_root, git_repo_url="", dump=False):
    """
    Deploy an entire directory tree.

    Args:
        api: ConfluenceAPI instance
        space_id: Target space ID
        root_path: Path to deploy (can be docs root or subfolder)
        docs_root: Root documentation directory
        git_repo_url: Git repository URL for CI banner
        dump: If True, write ADF JSON files and skip deployment
    """
    md_files = sorted(root_path.rglob("*.md"))

    # Filter out .page_content.md files (these are used for container pages)
    md_files = [f for f in md_files if f.name != ".page_content.md"]

    print(f"\n📚 Found {len(md_files)} markdown files in tree")

    for filepath in md_files:
        try:
            # Ensure page hierarchy exists
            if not dump:
                parent_id = ensure_page_hierarchy(api, space_id, filepath, root_path, git_repo_url)
            else:
                parent_id = None

            # Deploy the file
            deploy_page(api, space_id, parent_id, filepath, git_repo_url, dump=dump)
        except Exception as e:
            print(f"   ❌ Error: {e}")
            continue


def deploy_page(api, space_id, parent_id, filepath, git_repo_url="", dump=False):
    """
    Deploy a single markdown file to Confluence.

    CONFLUENCE API ATTACHMENT FLOW:
    Due to API limitations, we must:
    1. Create page first (gets pageId required for attachment collection)
    2. Upload attachments via v1 API (v2 lacks POST endpoint - CONFCLOUD-77196)
    3. Fetch Media Services fileIds via v2 GET (v1 upload doesn't return these)
    4. Update page with correct ADF media nodes containing fileIds

    Args:
        api: ConfluenceAPI instance
        space_id: Target space ID
        parent_id: Parent page ID (computed from folder hierarchy)
        filepath: Path to markdown file
        git_repo_url: Git repository URL for CI banner
        dump: If True, write ADF JSON to .adf.json file and skip deployment
    """
    print(f"\n📄 Processing: {filepath.name}")

    content = filepath.read_text()
    metadata, markdown = parse_frontmatter(content)

    # Check if page should be deployed
    if not metadata.get("deploy_page", True):
        print("   ⏭️  Skipping: deploy_page is set to false")
        return None

    title = metadata.get("title", filepath.stem.replace("-", " ").title())
    page_status = metadata.get("page_status", "current")
    print(f"   Title: {title}")
    print(f"   Status: {page_status}")

    file_git_url = f"{git_repo_url}/{filepath}" if git_repo_url else ""
    body = convert(markdown)

    # Add CI banner unless explicitly disabled
    if metadata.get("ci_banner", True):
        custom_banner_text = metadata.get("ci_banner_text")
        body = add_ci_banner(body, file_git_url, banner_text=custom_banner_text, metadata=metadata)

    # Resolve internal Confluence page links
    body = resolve_page_links(body, api, space_id)

    if dump:
        # Write ADF JSON to a file for inspection
        out = filepath.with_suffix(".adf.json")
        out.write_text(json.dumps(body, indent=2))
        print(f"   💾 ADF written to: {out}")
        print("   (Skipping deployment — remove --dump to deploy)")
        return None

    # Frontmatter parent override
    frontmatter_parent = metadata.get("parent")
    if frontmatter_parent:
        parent_page_id = api.find_page_by_title(space_id, frontmatter_parent)
        if parent_page_id:
            parent_id = parent_page_id
            print(f"   🔗 Parent override: '{frontmatter_parent}' (ID: {parent_page_id})")
        else:
            print(
                f"   ⚠️  Warning: Parent page '{frontmatter_parent}' not found, using directory hierarchy"
            )

    # STEP 1: Create or update page (images are still external URLs or placeholders)
    page_id = api.find_page_by_title(space_id, title)

    if page_id:
        print(f"   ♻️  Updating existing page (ID: {page_id})")
        api.update_page(page_id, title, body, status=page_status)
    else:
        print("   ✨ Creating new page")
        page_id = api.create_page(space_id, parent_id, title, body, status=page_status)

    # Prepare labels
    labels = metadata.get("labels", [])

    # Add author as label if present
    author = metadata.get("author")
    if author:
        # Convert "John Smith" to "author-john-smith"
        author_label = f"author-{author.lower().replace(' ', '-')}"
        labels.append(author_label)
        print(f"   👤 Author: {author}")

    api.add_labels(page_id, labels)
    all_labels = labels + ["managed-by-ci"]
    print(f"   🏷️  Labels: {', '.join(all_labels)}")

    # STEP 2: Upload attachments and collect Media Services fileIds
    attachments = metadata.get("attachments", [])
    if attachments:
        attachment_dir = filepath.parent.resolve()
        attachment_map = {}  # filename -> {id, fileId}

        for attachment in attachments:
            if isinstance(attachment, dict):
                raw_path = attachment["path"]
                att_path = (attachment_dir / raw_path).resolve()
                alt_text = attachment.get("alt", "")
                display_width = attachment.get("width")  # None → use default from converter
            else:
                raw_path = attachment
                att_path = (attachment_dir / raw_path).resolve()
                alt_text = None
                display_width = None

            # Validate resolved path stays within the attachment directory (path traversal guard)
            if not att_path.is_relative_to(attachment_dir):
                print(f"   ❌ Skipping unsafe attachment path: {raw_path}")
                continue

            if att_path.exists():
                print(f"   📎 Uploading: {att_path.name}")

                # Upload via v1 API (returns attachment ID but not fileId)
                upload_result = api.upload_attachment(page_id, att_path, alt_text)

                if upload_result and "results" in upload_result:
                    attachment_id = upload_result["results"][0]["id"]

                    # Fetch Media Services fileId via v2 API
                    print("   🔑 Fetching Media Services fileId...")
                    file_id = api.get_attachment_fileid(attachment_id)

                    if file_id:
                        attachment_map[att_path.name] = {
                            "id": attachment_id,
                            "fileId": file_id,
                            "display_width": display_width,
                        }
                        print(f"   ✓ Attachment ready: {att_path.name}")
                    else:
                        print(f"   ⚠️  Warning: Could not get fileId for {att_path.name}")
                else:
                    print(f"   ⚠️  Warning: Upload failed for {att_path.name}")
            else:
                print(f"   ⚠ Warning: Attachment not found: {att_path.name}")

        # STEP 3: Update page with correct ADF media nodes
        if attachment_map:
            from .transforms import resolve_attachment_media_nodes

            print("   🔗 Resolving attachment media nodes...")
            body_with_attachments = resolve_attachment_media_nodes(body, attachment_map, page_id)
            api.update_page(page_id, title, body_with_attachments, status=page_status)
            print(f"   ✓ Page updated with {len(attachment_map)} attachment(s)")

    print(f"   ✅ Success! Page ID: {page_id}")
    return page_id
