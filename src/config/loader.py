"""Loader for ccfm.yaml project configuration files.

ccfm.yaml is an optional project-level config that supplements or replaces CLI
arguments. CLI arguments always take precedence over config file values.

Supported schema:

    version: 1
    domain: company.atlassian.net
    email: ${CONFLUENCE_EMAIL}
    token: ${CONFLUENCE_TOKEN}
    space: DOCS
    docs_root: docs
    git_repo_url: https://github.com/org/repo
    state_file: .ccfm-state.json

    # Optional multi-space routing
    deployments:
      - directory: docs/public
        space: DOCS
      - directory: docs/internal
        space: INTERNAL

Environment variable interpolation: use ${VAR_NAME} anywhere in string values.
Missing variables are substituted with an empty string.

Security note: ccfm.yaml is a trusted-author file. Any env var visible to the
process can be interpolated into config values. Review ccfm.yaml changes in PRs
the same way you would review CI pipeline changes.
"""

import os
import re
from argparse import Namespace
from pathlib import Path

import yaml

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")

# Top-level config keys that map directly to CLI argument names
_CONFIG_TO_ARG = {
    "domain": "domain",
    "email": "email",
    "token": "token",
    "space": "space",
    "docs_root": "docs_root",
    "git_repo_url": "git_repo_url",
    "state_file": "state",
}


def interpolate_env(value: str) -> str:
    """Replace ${VAR_NAME} placeholders with environment variable values.

    Missing variables are substituted with an empty string.
    """
    return _ENV_VAR_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)


def _interpolate_recursive(obj: object) -> object:
    """Recursively interpolate env vars in all string values of a dict/list."""
    if isinstance(obj, str):
        return interpolate_env(obj)
    if isinstance(obj, dict):
        return {k: _interpolate_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate_recursive(item) for item in obj]
    return obj


def load_config(path: Path) -> dict:
    """Load and parse a ccfm.yaml file.

    Raises:
        FileNotFoundError: if the path does not exist.
        yaml.YAMLError: if the file is not valid YAML.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    return _interpolate_recursive(raw)


def merge_config_with_args(config: dict, args: Namespace) -> Namespace:
    """Merge config file values into CLI args. CLI args take precedence.

    A CLI arg is considered explicitly set if its current value is not None.
    Config values fill in gaps left by unset (None) CLI args. Boolean flags
    (--plan, --dump, --changed-only, --archive-orphans) are not in _CONFIG_TO_ARG
    and are not overrideable from the config file.

    The merged result is returned as a new Namespace.
    """
    merged = Namespace(**vars(args))

    for config_key, arg_name in _CONFIG_TO_ARG.items():
        if config_key not in config:
            continue
        current = getattr(merged, arg_name, None)
        if current is None:
            setattr(merged, arg_name, config[config_key])

    # docs_root may come back as a string from the config; coerce to Path
    if isinstance(getattr(merged, "docs_root", None), str):
        merged.docs_root = Path(merged.docs_root)

    return merged
