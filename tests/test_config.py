"""测试配置系统."""

import tempfile
from pathlib import Path

from momashuju.config import Config, _deep_merge, load_config


class TestDeepMerge:
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {
            "llm": {"model": "claude", "temp": 0.7},
            "rules": {"enabled": True},
        }
        override = {
            "llm": {"model": "deepseek"},
        }
        result = _deep_merge(base, override)
        assert result["llm"]["model"] == "deepseek"
        assert result["llm"]["temp"] == 0.7  # 保留
        assert result["rules"]["enabled"] is True


class TestConfig:
    def test_default_config(self):
        """验证默认配置可加载."""
        from momashuju.config import default_config

        assert default_config.llm["provider"] == "claude"
        assert "model" in default_config.llm
        assert default_config.rules is not None

    def test_dot_get(self):
        from momashuju.config import default_config

        assert default_config.get("llm.provider") == "claude"
        assert default_config.get("llm.nonexistent") is None
        assert default_config.get("llm.nonexistent", "default") == "default"

    def test_novel_config_override(self):
        """测试 novel.yaml 覆盖默认配置."""
        import tempfile
        import os

        # 创建临时 novel.yaml
        tmp_dir = tempfile.mkdtemp()
        novel_yaml = Path(tmp_dir) / "novel.yaml"
        novel_yaml.write_text("""
llm:
  model: claude-opus-4-8
  temperature: 0.5
rules:
  custom_banned:
    words:
      - "测试禁词"
""", encoding="utf-8")

        config = load_config(str(novel_yaml))
        assert config.get("llm.model") == "claude-opus-4-8"
        assert config.get("llm.temperature") == 0.5
        assert config.get("llm.provider") == "claude"  # 未被覆盖，保留默认
        assert "测试禁词" in config.get("rules.custom_banned.words")

        # clean up
        novel_yaml.unlink()
        os.rmdir(tmp_dir)

    def test_load_nonexistent(self):
        """测试加载不存在的配置路径 — 应回退到默认."""
        config = load_config("/nonexistent/path/novel.yaml")
        from momashuju.config import default_config
        assert config.llm["provider"] == default_config.llm["provider"]
