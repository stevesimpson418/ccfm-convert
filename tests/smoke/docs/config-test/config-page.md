---
page_meta:
  title: CCFM Smoke Test — Config File Deploy
  labels:
    - ccfm-smoke-test

deploy_config:
  ci_banner: false
---

# CCFM Smoke Test — Config File Deploy

This page is deployed by the config-file smoke test to verify that `ccfm.yaml` with
`${ENV_VAR}` interpolation works correctly end-to-end.

The deploy uses `--config ccfm-smoke.yaml` instead of inline CLI credentials.
