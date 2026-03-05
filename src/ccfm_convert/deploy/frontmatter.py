"""YAML Frontmatter Parsing."""

import yaml


def parse_frontmatter(content):
    """
    Extract YAML frontmatter and content from markdown.

    Expected structure:
      page_meta:
        title: My Page
        author: John Smith
        labels: [tag1, tag2]
        attachments: [...]
      deploy_config:
        ci_banner: true
        ci_banner_text: "..."
        include_page_metadata: true
        page_status: "current"
        deploy_page: true

    Returns:
        (metadata_dict, markdown_content)
    """
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        raw_metadata = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        print(f"Error parsing frontmatter: {e}")
        return {}, content

    # Extract from nested structure
    page_meta = raw_metadata.get("page_meta", {})
    deploy_config = raw_metadata.get("deploy_config", {})

    # Build normalized metadata
    metadata = {
        # Page metadata
        "title": page_meta.get("title"),
        "author": page_meta.get("author"),
        "labels": page_meta.get("labels", []),
        "attachments": page_meta.get("attachments", []),
        "parent": page_meta.get("parent"),
        # Deploy config with defaults
        "ci_banner": deploy_config.get("ci_banner", True),
        "ci_banner_text": deploy_config.get("ci_banner_text"),
        "include_page_metadata": deploy_config.get("include_page_metadata", False),
        "page_status": deploy_config.get("page_status", "current"),
        "deploy_page": deploy_config.get("deploy_page", True),
    }

    # Validate page_status
    if metadata.get("page_status") not in ["current", "draft"]:
        print(f"⚠️  Warning: Invalid page_status '{metadata.get('page_status')}', using 'current'")
        metadata["page_status"] = "current"

    return metadata, parts[2].strip()
