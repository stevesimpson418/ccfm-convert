"""Tests for config.loader module."""

from argparse import Namespace
from pathlib import Path

import pytest
import yaml

from ccfm_convert.config.loader import (
    ConfigValidationError,
    interpolate_env,
    load_config,
    merge_config_with_args,
)


class TestInterpolateEnv:
    def test_no_placeholder_returns_unchanged(self):
        """Plain strings without ${} pass through untouched."""
        assert interpolate_env("hello world") == "hello world"

    def test_known_env_var_is_substituted(self, monkeypatch):
        """${VAR} is replaced with the env var value (line 54)."""
        monkeypatch.setenv("MY_TOKEN", "secret123")
        result = interpolate_env("Bearer ${MY_TOKEN}")
        assert result == "Bearer secret123"

    def test_missing_env_var_becomes_empty_string(self, monkeypatch):
        """${MISSING} with no env var becomes empty string."""
        monkeypatch.delenv("TOTALLY_ABSENT_VAR", raising=False)
        result = interpolate_env("prefix-${TOTALLY_ABSENT_VAR}-suffix")
        assert result == "prefix--suffix"

    def test_multiple_placeholders_in_one_string(self, monkeypatch):
        monkeypatch.setenv("USER", "alice")
        monkeypatch.setenv("HOST", "example.com")
        result = interpolate_env("${USER}@${HOST}")
        assert result == "alice@example.com"


class TestInterpolateRecursive:
    """Covered indirectly via load_config, but also via direct calls through loader internals."""

    def test_dict_values_are_interpolated(self, monkeypatch, tmp_path):
        """Dict string values get env-var substitution (lines 61-62)."""
        monkeypatch.setenv("CONF_TOKEN", "tok123")
        cfg_file = tmp_path / "ccfm.yaml"
        cfg_file.write_text("version: 1\ntoken: ${CONF_TOKEN}\n", encoding="utf-8")
        result = load_config(cfg_file)
        assert result["token"] == "tok123"

    def test_list_items_are_interpolated(self, monkeypatch, tmp_path):
        """List string items get env-var substitution (lines 63-64)."""
        monkeypatch.setenv("SPACE_KEY", "MYSPACE")
        cfg_file = tmp_path / "ccfm.yaml"
        cfg_file.write_text(
            "version: 1\ndeployments:\n  - ${SPACE_KEY}\n  - FIXED\n", encoding="utf-8"
        )
        result = load_config(cfg_file)
        assert result["deployments"] == ["MYSPACE", "FIXED"]

    def test_non_string_values_are_returned_unchanged(self, tmp_path):
        """Integers and booleans pass through _interpolate_recursive unchanged (line 65)."""
        cfg_file = tmp_path / "ccfm.yaml"
        cfg_file.write_text("version: 1\n", encoding="utf-8")
        result = load_config(cfg_file)
        assert result["version"] == 1


class TestLoadConfig:
    def test_load_config_raises_when_file_missing(self, tmp_path):
        """FileNotFoundError when path does not exist (lines 75-76)."""
        missing = tmp_path / "no_such.yaml"
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(missing)

    def test_load_config_parses_valid_yaml(self, tmp_path):
        """load_config reads and returns parsed YAML dict (lines 78-81)."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text("version: 1\ndomain: example.atlassian.net\nspace: DOCS\n", encoding="utf-8")
        result = load_config(cfg)
        assert result["domain"] == "example.atlassian.net"
        assert result["space"] == "DOCS"

    def test_load_config_empty_file_returns_empty_dict(self, tmp_path):
        """Empty YAML file returns {} (yaml.safe_load returns None → `or {}`)."""
        cfg = tmp_path / "empty.yaml"
        cfg.write_text("", encoding="utf-8")
        result = load_config(cfg)
        assert result == {}

    def test_load_config_interpolates_env_vars(self, monkeypatch, tmp_path):
        """load_config runs _interpolate_recursive on the parsed data (line 81)."""
        monkeypatch.setenv("CONFLUENCE_EMAIL", "user@example.com")
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text("version: 1\nemail: ${CONFLUENCE_EMAIL}\n", encoding="utf-8")
        result = load_config(cfg)
        assert result["email"] == "user@example.com"

    def test_load_config_raises_on_invalid_yaml(self, tmp_path):
        """yaml.YAMLError propagates for malformed YAML files."""
        cfg = tmp_path / "bad.yaml"
        # This produces a scanner error
        cfg.write_text("key: [\n  unclosed", encoding="utf-8")
        with pytest.raises(yaml.YAMLError):
            load_config(cfg)


class TestMergeConfigWithArgs:
    def test_config_fills_missing_cli_arg(self):
        """Config value is applied when CLI arg is None."""
        config = {"domain": "from-config.atlassian.net"}
        args = Namespace(domain=None, email=None, token=None, space=None, docs_root=None)
        merged = merge_config_with_args(config, args)
        assert merged.domain == "from-config.atlassian.net"

    def test_cli_arg_takes_precedence_over_config(self):
        """Explicit CLI value is NOT overwritten by config."""
        config = {"domain": "from-config.atlassian.net"}
        args = Namespace(
            domain="cli.atlassian.net",
            email=None,
            token=None,
            space=None,
            docs_root=None,
        )
        merged = merge_config_with_args(config, args)
        assert merged.domain == "cli.atlassian.net"

    def test_config_key_not_present_is_skipped(self):
        """Missing config keys leave args unchanged."""
        config = {}
        args = Namespace(domain=None, email=None, token=None, space=None, docs_root=None)
        merged = merge_config_with_args(config, args)
        assert merged.domain is None

    def test_docs_root_string_coerced_to_path(self):
        """docs_root string from config is converted to Path."""
        config = {"docs_root": "my/docs"}
        args = Namespace(domain=None, email=None, token=None, space=None, docs_root=None)
        merged = merge_config_with_args(config, args)
        assert merged.docs_root == Path("my/docs")
        assert isinstance(merged.docs_root, Path)

    def test_docs_root_already_path_is_not_double_wrapped(self):
        """When docs_root is already a Path, no re-wrapping occurs."""
        config = {}
        args = Namespace(
            domain=None,
            email=None,
            token=None,
            space=None,
            docs_root=Path("already/a/path"),
        )
        merged = merge_config_with_args(config, args)
        assert merged.docs_root == Path("already/a/path")

    def test_original_namespace_is_not_mutated(self):
        """merge_config_with_args returns a new Namespace, not mutating input."""
        config = {"domain": "new.atlassian.net"}
        args = Namespace(domain=None, email=None, token=None, space=None, docs_root=None)
        merge_config_with_args(config, args)
        assert args.domain is None

    def test_all_config_keys_are_applied(self):
        """All _CONFIG_TO_ARG mappings are exercised in one pass."""
        config = {
            "domain": "d.atlassian.net",
            "email": "e@example.com",
            "token": "tok",
            "space": "SP",
            "docs_root": "docs",
            "git_repo_url": "https://github.com/org/repo",
        }
        args = Namespace(
            domain=None,
            email=None,
            token=None,
            space=None,
            docs_root=None,
            git_repo_url=None,
        )
        merged = merge_config_with_args(config, args)
        assert merged.domain == "d.atlassian.net"
        assert merged.email == "e@example.com"
        assert merged.token == "tok"
        assert merged.space == "SP"
        assert merged.docs_root == Path("docs")
        assert merged.git_repo_url == "https://github.com/org/repo"

    def test_docs_root_from_config_sets_path(self):
        """docs_root from config is coerced to Path."""
        config = {"docs_root": "docs"}
        args = Namespace(domain=None, email=None, token=None, space=None, docs_root=None)
        merged = merge_config_with_args(config, args)
        assert merged.docs_root == Path("docs")

    def test_docs_root_from_cli_takes_precedence(self):
        """CLI --docs-root takes precedence over config docs_root."""
        config = {"docs_root": "config-docs"}
        args = Namespace(
            domain=None, email=None, token=None, space=None, docs_root=Path("cli-docs")
        )
        merged = merge_config_with_args(config, args)
        assert merged.docs_root == Path("cli-docs")


class TestConfigValidation:
    def test_valid_config_keys_accepted(self, tmp_path):
        """All recognised top-level keys pass validation."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text(
            "version: 1\ndomain: x.atlassian.net\nemail: a@b.com\n"
            "token: tok\nspace: SP\ndocs_root: docs\ngit_repo_url: https://gh.com/o/r\n",
            encoding="utf-8",
        )
        result = load_config(cfg)
        assert result["domain"] == "x.atlassian.net"

    def test_deployments_key_accepted(self, tmp_path):
        """The 'deployments' future key is accepted without error."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text(
            "version: 1\ndomain: x.atlassian.net\ndeployments:\n  - space: SP\n",
            encoding="utf-8",
        )
        result = load_config(cfg)
        assert "deployments" in result

    def test_nested_confluence_key_rejected(self, tmp_path):
        """Nested 'confluence:' structure raises ConfigValidationError."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text(
            "confluence:\n  domain: x.atlassian.net\n  email: a@b.com\n",
            encoding="utf-8",
        )
        with pytest.raises(
            ConfigValidationError, match="Unrecognised top-level keys.*'confluence'"
        ):
            load_config(cfg)

    def test_multiple_unknown_keys_all_reported(self, tmp_path):
        """All unrecognised keys are listed in the error message."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text(
            "confluence:\n  domain: x\nspace:\n  key: SP\ndocumentation:\n  root: docs\n",
            encoding="utf-8",
        )
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(cfg)
        msg = str(exc_info.value)
        assert "'confluence'" in msg
        assert "'documentation'" in msg
        # 'space' is a valid key — verify it's not in the unrecognised portion
        unrecognised_part = msg.split("Valid keys")[0]
        assert "'space'" not in unrecognised_part

    def test_error_message_includes_valid_keys(self, tmp_path):
        """Error message lists the valid keys for guidance."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text("bogus: true\n", encoding="utf-8")
        with pytest.raises(ConfigValidationError, match="Valid keys are:"):
            load_config(cfg)

    def test_error_message_includes_docs_url(self, tmp_path):
        """Error message includes a link to the docs site."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text("bogus: true\n", encoding="utf-8")
        with pytest.raises(ConfigValidationError, match="https://ccfm.io/configuration/"):
            load_config(cfg)

    def test_empty_config_passes_validation(self, tmp_path):
        """An empty config file passes validation (no keys to reject)."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text("", encoding="utf-8")
        result = load_config(cfg)
        assert result == {}

    def test_state_file_key_rejected(self, tmp_path):
        """Legacy state_file config key is rejected by the validator."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text("version: 1\nstate_file: .my-state.json\n", encoding="utf-8")
        with pytest.raises(ConfigValidationError, match="'state_file'"):
            load_config(cfg)

    def test_single_unknown_key_with_valid_keys(self, tmp_path):
        """One unknown key alongside valid keys is caught."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text("version: 1\ndomain: x.atlassian.net\nfoo: bar\n", encoding="utf-8")
        with pytest.raises(ConfigValidationError, match="'foo'"):
            load_config(cfg)

    def test_scalar_yaml_raises_validation_error(self, tmp_path):
        """A YAML file containing only a scalar value raises ConfigValidationError."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text("just a string\n", encoding="utf-8")
        with pytest.raises(ConfigValidationError, match="must contain key-value pairs"):
            load_config(cfg)

    def test_list_yaml_raises_validation_error(self, tmp_path):
        """A YAML file containing a list at the top level raises ConfigValidationError."""
        cfg = tmp_path / "ccfm.yaml"
        cfg.write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(ConfigValidationError, match="must contain key-value pairs"):
            load_config(cfg)
