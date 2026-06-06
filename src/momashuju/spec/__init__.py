"""Spec 层 — 数据模型、模板与加载器."""

from momashuju.spec.models import (
    ChapterOutline,
    Character,
    Foreshadowing,
    ForeshadowingTracker,
    StyleConstraints,
    WorldSetting,
)
from momashuju.spec.templates import (
    create_character_template,
    create_outline_template,
    create_world_template,
)
from momashuju.spec.loader import load_novel_project, NovelProject

__all__ = [
    # models
    "WorldSetting",
    "Character",
    "ChapterOutline",
    "StyleConstraints",
    "Foreshadowing",
    "ForeshadowingTracker",
    # templates
    "create_world_template",
    "create_character_template",
    "create_outline_template",
    # loader
    "load_novel_project",
    "NovelProject",
]
