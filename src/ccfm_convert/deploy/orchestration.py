"""Deployment Orchestration."""

from pathlib import Path

from ccfm_convert.adf import convert

from .frontmatter import parse_frontmatter
from .transforms import add_ci_banner, resolve_page_links


def ensure_page_hierarchy(api, space_id, filepath, docs_root, git_repo_url="", ci_banner_text=None):
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
        ci_banner_text: Optional global CI banner text from ccfm.yaml

    Returns:
        Tuple of (parent_page_id, hierarchy_pages) where hierarchy_pages is a list of
        (rel_path, page_id, title) for each directory container page created/found.
    """
    # Get relative path from docs root
    try:
        rel_path = filepath.relative_to(docs_root)
    except ValueError:
        # File is not under docs_root
        return None, []

    # Get directory path (everything except the filename)
    dir_path = rel_path.parent

    # If file is directly in docs root, no parent needed
    if str(dir_path) == ".":
        return None, []

    # Create each directory as a page in the hierarchy
    parts = dir_path.parts
    current_parent_id = None
    hierarchy_pages: list[tuple[str, str, str]] = []

    docs_root_resolved = docs_root.resolve()

    for i, dir_name in enumerate(parts):
        # Build path to this directory
        current_dir = docs_root / Path(*parts[: i + 1])

        # Guard against symlinks that point outside docs_root
        if not current_dir.resolve().is_relative_to(docs_root_resolved):
            raise ValueError(
                f"Directory '{current_dir}' resolves outside docs_root '{docs_root}'. "
                "Symlinks that escape the docs root are not permitted."
            )

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
            file_git_url = f"{git_repo_url}/{page_content_file}" if git_repo_url else ""
            body = add_ci_banner(body, metadata, file_git_url, global_ci_banner_text=ci_banner_text)

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

        # Check if page already exists — scope to parent when possible
        if current_parent_id:
            page_id = api.find_child_page_by_title(current_parent_id, title)
        else:
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

        # Record the hierarchy page using its path relative to cwd
        try:
            dir_rel_path = str(current_dir.resolve().relative_to(Path.cwd().resolve()))
        except ValueError:
            dir_rel_path = str(current_dir)
        hierarchy_pages.append((dir_rel_path, current_parent_id, title))

    return current_parent_id, hierarchy_pages


def deploy_tree(api, space_id, docs_root, git_repo_url="", files=None, ci_banner_text=None):
    """
    Deploy an entire directory tree.

    Args:
        api: ConfluenceAPI instance
        space_id: Target space ID
        docs_root: Root documentation directory
        git_repo_url: Git repository URL for CI banner
        files: Optional pre-filtered list of files to deploy. When provided,
            only these files are deployed instead of discovering all .md files
            via rglob. Used by apply to limit deployment to actionable files.
        ci_banner_text: Optional global CI banner text from ccfm.yaml.
            Per-page frontmatter ci_banner_text takes precedence.

    Returns:
        Tuple of (results, hierarchy_pages) where results is a list of
        (filepath, page_id) tuples and hierarchy_pages is a deduplicated list of
        (rel_path, page_id, title) for each directory container page.
    """
    if files is not None:
        md_files = sorted(files)
    else:
        md_files = sorted(docs_root.rglob("*.md"))

    # Filter out .page_content.md files (these are used for container pages)
    md_files = [f for f in md_files if f.name != ".page_content.md"]

    print(f"\n📚 Found {len(md_files)} markdown files in tree")

    results: list[tuple[Path, str | None]] = []
    all_hierarchy_pages: list[tuple[str, str, str]] = []
    seen_dirs: set[str] = set()

    for filepath in md_files:
        try:
            parent_id, h_pages = ensure_page_hierarchy(
                api, space_id, filepath, docs_root, git_repo_url, ci_banner_text=ci_banner_text
            )
            for hp in h_pages:
                if hp[0] not in seen_dirs:
                    all_hierarchy_pages.append(hp)
                    seen_dirs.add(hp[0])

            page_id = deploy_page(
                api, space_id, parent_id, filepath, git_repo_url, ci_banner_text=ci_banner_text
            )
            results.append((filepath, page_id))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append((filepath, None))
            continue

    return results, all_hierarchy_pages


def destroy_page(api, page_id: str, title: str) -> bool:
    """Delete a Confluence page (moves it to the site trash).

    The Confluence Cloud v2 API does not support ``status: archived`` via the
    PUT pages endpoint (only ``CURRENT`` and ``DRAFT`` are accepted). Instead,
    we use the v2 DELETE endpoint, which moves the page to the site trash.

    Used to clean up pages whose source markdown files have been deleted.

    Args:
        api: ConfluenceAPI instance
        page_id: ID of the page to delete
        title: Page title (used only for logging)

    Returns:
        True if the operation succeeded, False otherwise.
    """
    try:
        api.delete_page(page_id)
        print(f"   🗑️  Destroyed page: '{title}' (ID: {page_id})")
        return True
    except Exception as e:
        print(f"   ⚠️  Could not destroy '{title}' (ID: {page_id}): {e}")
        return False


def destroy_pages(api, state, destroy_actions) -> int:
    """Execute destroy actions — delete pages and remove from state.

    Actions are expected to be pre-sorted deepest-first by the planner
    (children before parents) to avoid Confluence errors when deleting
    parent pages with children.

    Args:
        api: ConfluenceAPI instance
        state: StateManager instance
        destroy_actions: list of DestroyAction objects (pre-sorted by planner)

    Returns:
        Number of successfully destroyed pages.
    """
    destroyed = 0
    for action in destroy_actions:
        if destroy_page(api, action.page_id, action.title):
            state.remove_page(action.rel_path)
            destroyed += 1
    return destroyed


def deploy_page(api, space_id, parent_id, filepath, git_repo_url="", ci_banner_text=None):
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
        ci_banner_text: Optional global CI banner text from ccfm.yaml.
            Per-page frontmatter ci_banner_text takes precedence.
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
    body = add_ci_banner(body, metadata, file_git_url, global_ci_banner_text=ci_banner_text)

    # Resolve internal Confluence page links
    body = resolve_page_links(body, api, space_id)

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
    # Scope lookup to parent when available to avoid matching same-titled pages elsewhere
    if parent_id:
        page_id = api.find_child_page_by_title(parent_id, title)
    else:
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
