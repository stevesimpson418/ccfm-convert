---
page_meta:
  title: CCFM Smoke Test — Single Page
  labels:
    - ccfm-smoke-test

deploy_config:
  ci_banner: false
---

# CCFM Smoke Test — Single Page

This page is deployed by the CCFM smoke test suite to verify that single-file deployment
via `--file` works correctly end-to-end.

## Features exercised

- Frontmatter parsing (`page_meta`, `deploy_config`)
- Labels attachment
- Basic markdown conversion: **bold**, *italic*, `inline code`

## Content

This page is intentionally simple. For a comprehensive feature exercise see the
`complete_example.md` file in the `example/` directory.
