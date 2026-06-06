"""Spec 加载器 — 从目录或文件加载完整小说项目 spec."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from momashuju.spec.models import (
    ChapterOutline,
    Character,
    ForeshadowingTracker,
    Relationship,
    StyleConstraints,
    WorldSetting,
)


@dataclass
class NovelProject:
    """完整的 Spec 层数据."""

    title: str = ""
    author: str = ""
    summary: str = ""
    genre: str = ""

    world: WorldSetting = field(default_factory=WorldSetting)
    characters: list[Character] = field(default_factory=list)
    chapters: list[ChapterOutline] = field(default_factory=list)
    style: StyleConstraints = field(default_factory=StyleConstraints)
    foreshadowing: ForeshadowingTracker = field(default_factory=ForeshadowingTracker)
    raw_config: dict[str, Any] = field(default_factory=dict)


def load_novel_project(project_dir: str | Path) -> NovelProject:
    """从项目目录加载完整的 novel spec.

    目录结构预期:
        project_dir/
            novel.yaml        # 小说元信息 + 风格约束
            world.yaml        # 世界观设定
            characters.yaml   # 角色档案列表
            outline.yaml      # 章节大纲列表

    Args:
        project_dir: 小说项目目录路径

    Returns:
        NovelProject: 完整的 spec 数据
    """
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"项目目录不存在: {project_dir}")

    project = NovelProject()

    # 1. 加载 novel.yaml
    novel_path = project_dir / "novel.yaml"
    if novel_path.exists():
        novel_data = _read_yaml(novel_path)
        project.raw_config = novel_data
        project.title = novel_data.get("title", "")
        project.author = novel_data.get("author", "")
        project.summary = novel_data.get("summary", "")
        project.genre = novel_data.get("genre", "")

        # 解析风格约束
        style_data = novel_data.get("style", {})
        if style_data:
            project.style = StyleConstraints(**style_data)

    # 2. 加载 world.yaml
    world_path = project_dir / "world.yaml"
    if world_path.exists():
        world_data = _read_yaml(world_path)
        project.world = WorldSetting(**world_data)

    # 3. 加载 characters.yaml
    chars_path = project_dir / "characters.yaml"
    if chars_path.exists():
        chars_data = _read_yaml(chars_path)
        # 支持顶层 'characters' 列表或直接列表
        char_list = chars_data if isinstance(chars_data, list) else chars_data.get("characters", [])
        for cdata in char_list:
            # 将 relationships 子对象转换为 Relationship 模型
            if "relationships" in cdata and isinstance(cdata["relationships"], list):
                cdata["relationships"] = [
                    Relationship(**r) if isinstance(r, dict) else r
                    for r in cdata["relationships"]
                ]
            project.characters.append(Character(**cdata))

    # 4. 加载 outline.yaml
    outline_path = project_dir / "outline.yaml"
    if outline_path.exists():
        outline_data = _read_yaml(outline_path)
        chapter_list = outline_data if isinstance(outline_data, list) else outline_data.get("chapters", [])
        for ch_data in chapter_list:
            project.chapters.append(ChapterOutline(**ch_data))

    return project


def _read_yaml(path: Path) -> dict:
    """读取 YAML 文件，返回字典。空文件返回 {}."""
    with open(path, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f)
    return content if content is not None else {}
