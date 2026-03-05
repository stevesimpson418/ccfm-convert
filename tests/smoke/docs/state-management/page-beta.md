---
page_meta:
  title: CCFM Smoke Test — Page Beta
  labels:
    - ccfm-smoke-test

deploy_config:
  ci_banner: false
---

# CCFM Smoke Test — Page Beta

This page is used by the state management smoke tests to exercise `--archive-orphans`.

The test deploys this page, then simulates its removal by running `--archive-orphans`
against a directory that no longer includes it. The resulting Confluence page should be
archived and the state entry removed.
