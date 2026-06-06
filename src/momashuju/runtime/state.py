"""状态持久化 — checkpoint 读写 + 项目状态管理.

每章输出保存为 YAML，状态快照支持断点续写。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from momashuju.runtime.context import ChapterSummary, ContextManager
from momashuju.spec.models import ChapterContent, Foreshadowing, ForeshadowingStatus, ForeshadowingTracker


def _fs_to_dict(fs: Foreshadowing | dict) -> dict:
    """将 Foreshadowing 转为纯 dict，枚举值序列化为字符串."""
    if isinstance(fs, dict):
        return fs
    d = fs.model_dump()
    # 确保 status 是字符串
    if isinstance(d.get("status"), ForeshadowingStatus):
        d["status"] = d["status"].value
    return d


@dataclass
class ProjectState:
    """可持久化的项目运行状态."""

    novel_title: str = ""
    current_chapter: int = 0
    character_states: dict[str, str] = field(default_factory=dict)
    chapter_summaries: list[dict[str, Any]] = field(default_factory=list)
    foreshadowings: list[dict[str, Any]] = field(default_factory=list)
    completed_chapters: list[int] = field(default_factory=list)


class StateManager:
    """管理 checkpoint 和项目状态的持久化."""

    def __init__(self, output_dir: str | Path) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    # ── 章节级别 ──

    def save_chapter(self, content: ChapterContent) -> Path:
        """保存单章正文到 YAML.

        路径：output/{novel}/ch{NNN}.yaml
        """
        filename = f"ch{content.chapter_number:03d}.yaml"
        filepath = self._output_dir / filename

        data = {
            "chapter_number": content.chapter_number,
            "title": content.title,
            "content": content.content,
            "word_count": content.word_count,
            "summary": content.summary,
            "character_state_updates": content.character_state_updates,
            "foreshadowing_updates": [
                _fs_to_dict(fs) for fs in content.foreshadowing_updates
            ],
            "notes": content.notes,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return filepath

    def load_chapter(self, chapter_num: int) -> ChapterContent | None:
        """加载单章.

        Args:
            chapter_num: 章节序号

        Returns:
            ChapterContent 或 None（文件不存在）
        """
        filepath = self._output_dir / f"ch{chapter_num:03d}.yaml"
        if not filepath.exists():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return None

        return ChapterContent(
            chapter_number=data.get("chapter_number", chapter_num),
            title=data.get("title", ""),
            content=data.get("content", ""),
            word_count=data.get("word_count", 0),
            summary=data.get("summary", ""),
            character_state_updates=data.get("character_state_updates", {}),
            foreshadowing_updates=data.get("foreshadowing_updates", []),
            notes=data.get("notes", ""),
        )

    # ── 项目状态级别 ──

    def save_project_state(
        self,
        context_mgr: ContextManager,
        novel_title: str = "",
        current_chapter: int = 0,
        completed_chapters: list[int] | None = None,
    ) -> Path:
        """保存项目状态快照为 checkpoint.yaml.

        用于断点续写时恢复 ContextManager 状态。
        """
        filepath = self._output_dir / "checkpoint.yaml"

        state = ProjectState(
            novel_title=novel_title,
            current_chapter=current_chapter,
            character_states=context_mgr._character_states,
            chapter_summaries=[
                {
                    "chapter_number": s.chapter_number,
                    "title": s.title,
                    "summary": s.summary,
                    "key_events": s.key_events,
                    "character_changes": s.character_changes,
                    "foreshadowing_updates": s.foreshadowing_updates,
                }
                for s in context_mgr._chapter_summaries
            ],
            foreshadowings=[
                _fs_to_dict(fs)
                for fs in context_mgr._foreshadowings
            ],
            completed_chapters=completed_chapters or [],
        )

        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(state.__dict__, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return filepath

    def load_project_state(self) -> ProjectState | None:
        """加载项目状态快照.

        Returns:
            ProjectState 或 None（checkpoint 不存在）
        """
        filepath = self._output_dir / "checkpoint.yaml"
        if not filepath.exists():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return None

        return ProjectState(
            novel_title=data.get("novel_title", ""),
            current_chapter=data.get("current_chapter", 0),
            character_states=data.get("character_states", {}),
            chapter_summaries=data.get("chapter_summaries", []),
            foreshadowings=data.get("foreshadowings", []),
            completed_chapters=data.get("completed_chapters", []),
        )

    def restore_context(self, context_mgr: ContextManager) -> bool:
        """从 checkpoint 恢复 ContextManager 状态.

        Returns:
            True 如果成功恢复，False 如果没有 checkpoint
        """
        state = self.load_project_state()
        if state is None:
            return False

        # 恢复角色状态
        context_mgr._character_states = state.character_states

        # 恢复章节摘要
        context_mgr._chapter_summaries = [
            ChapterSummary(**s) for s in state.chapter_summaries
        ]

        # 恢复伏笔
        from momashuju.spec.models import ForeshadowingStatus
        context_mgr._foreshadowings = [
            Foreshadowing(**fs) for fs in state.foreshadowings
        ]

        return True

    def get_completed_chapters(self) -> list[int]:
        """扫描 output 目录，查找已完成的章节序号."""
        chapters = []
        for f in self._output_dir.glob("ch*.yaml"):
            if f.name == "checkpoint.yaml":
                continue
            try:
                num = int(f.stem.replace("ch", ""))
                chapters.append(num)
            except ValueError:
                continue
        return sorted(chapters)

    def get_next_chapter(self, total_chapters: int) -> int | None:
        """确定下一个待写的章节序号.

        Returns:
            下一个章节号（1-based），如果全部完成则返回 None
        """
        completed = self.get_completed_chapters()
        if not completed:
            return 1
        last = max(completed)
        next_ch = last + 1
        return next_ch if next_ch <= total_chapters else None
