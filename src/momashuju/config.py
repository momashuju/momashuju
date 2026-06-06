"""配置系统 — YAML 加载、默认值合并、路径解析."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个字典，override 的值优先."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    """全局配置对象，从 YAML 加载并支持多层合并.

    合并优先级（由低到高）:
    1. defaults.yaml（包内置默认值）
    2. novel.yaml（小说项目级配置）
    """

    def __init__(self, data: dict) -> None:
        self._data = data

    # ── 便捷属性 ──

    @property
    def llm(self) -> dict:
        return self._data.get("llm", {})

    @property
    def context(self) -> dict:
        return self._data.get("context", {})

    @property
    def rules(self) -> dict:
        return self._data.get("rules", {})

    @property
    def scoring(self) -> dict:
        return self._data.get("scoring", {})

    @property
    def paths(self) -> dict:
        return self._data.get("paths", {})

    # ── 通用访问 ──

    def get(self, key: str, default: Any = None) -> Any:
        """用点号分隔的 key 获取嵌套值，如 'llm.model'."""
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def to_dict(self) -> dict:
        return self._data

    def __repr__(self) -> str:
        return f"Config(llm={self.get('llm.provider')}:{self.get('llm.model')})"


def _load_defaults() -> dict:
    """加载内置 defaults.yaml."""
    defaults_path = Path(__file__).parent / "defaults.yaml"
    with open(defaults_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(novel_config_path: str | Path | None = None) -> Config:
    """加载配置：默认值 + 可选的小说项目配置.

    Args:
        novel_config_path: 可选，novel.yaml 路径。

    Returns:
        合并后的 Config 对象。
    """
    data = _load_defaults()

    if novel_config_path:
        novel_path = Path(novel_config_path)
        if novel_path.exists():
            with open(novel_path, "r", encoding="utf-8") as f:
                novel_data = yaml.safe_load(f) or {}
            data = _deep_merge(data, novel_data)

    # 解析路径（相对于项目根目录）
    project_root = _find_project_root()
    paths = data.setdefault("paths", {})
    for key in ("novels_dir", "output_dir", "checkpoints_dir"):
        if key in paths and not os.path.isabs(paths[key]):
            paths[key] = str(project_root / paths[key])

    return Config(data)


def _find_project_root() -> Path:
    """查找项目根目录（包含 pyproject.toml 或 README.md 的目录）."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists() or (parent / "README.md").exists():
            return parent
    return current


# 模块级默认配置（无 novel 覆盖）
default_config = load_config()
