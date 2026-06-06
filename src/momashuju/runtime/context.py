"""上下文管理 — 动态压缩 + 状态摘要.

核心设计：
- 不携带全文上下文
- 仅携带：角色状态 + 前 N 章摘要 + 伏笔清单 + 当前章目标
"""

from __future__ import annotations

from dataclasses import dataclass, field

from momashuju.spec.models import ChapterOutline, Character, Foreshadowing


@dataclass
class ChapterSummary:
    """单章摘要（用于上下文压缩）."""

    chapter_number: int
    title: str
    summary: str                     # 本章内容摘要
    key_events: list[str] = field(default_factory=list)
    character_changes: dict[str, str] = field(default_factory=dict)  # 角色名 → 状态变化
    foreshadowing_updates: list[str] = field(default_factory=list)   # 伏笔更新


@dataclass
class AssembledContext:
    """组装好的写作上下文，传入 WriterAgent."""

    # 当前章目标
    current_outline: ChapterOutline | None = None

    # 角色当前状态（姓名 → 状态摘要文本）
    character_states: dict[str, str] = field(default_factory=dict)

    # 最近 N 章摘要
    recent_summaries: list[ChapterSummary] = field(default_factory=list)

    # 未回收的伏笔
    unresolved_foreshadowing: list[Foreshadowing] = field(default_factory=list)

    # 风格约束
    style_notes: str = ""

    # 世界规则提示
    world_rules: list[str] = field(default_factory=list)


class ContextManager:
    """管理写作上下文的生命周期.

    职责：
    1. 从已完成的章节中提取/更新角色状态
    2. 生成最近 N 章摘要
    3. 跟踪伏笔状态
    4. 组装当前章的写作上下文
    """

    def __init__(self, max_history: int = 3):
        self.max_history = max_history
        self._chapter_summaries: list[ChapterSummary] = []
        self._character_states: dict[str, str] = {}
        self._foreshadowings: list[Foreshadowing] = []

    def update_after_chapter(self, summary: ChapterSummary) -> None:
        """完成一章后更新状态."""
        self._chapter_summaries.append(summary)
        # 只保留最近 N 章
        if len(self._chapter_summaries) > self.max_history:
            self._chapter_summaries = self._chapter_summaries[-self.max_history:]

        # 合并角色状态
        for name, change in summary.character_changes.items():
            self._character_states[name] = change

    def register_foreshadowing(self, fs: Foreshadowing) -> None:
        """注册新伏笔."""
        self._foreshadowings.append(fs)

    def resolve_foreshadowing(self, fs_id: str) -> None:
        """标记伏笔已回收."""
        for f in self._foreshadowings:
            if f.id == fs_id:
                f.status = "resolved"
                return

    def get_unresolved_foreshadowings(self) -> list[Foreshadowing]:
        """获取所有未回收伏笔."""
        return [f for f in self._foreshadowings if f.status != "resolved"]

    def assemble_context(
        self,
        outline: ChapterOutline,
        characters: list[Character],
        style_notes: str = "",
        world_rules: list[str] | None = None,
    ) -> AssembledContext:
        """组装当前章的完整写作上下文.

        Args:
            outline: 当前章大纲
            characters: 全角色列表
            style_notes: 风格约束说明
            world_rules: 世界规则列表

        Returns:
            组装好的写作上下文
        """
        # 初始化角色状态（首次写作时）
        if not self._character_states:
            for char in characters:
                self._character_states[char.name] = (
                    f"{char.name}：{char.personality}。{char.appearance}。{char.desire}"
                )

        # 需要当前章关注的伏笔
        unresolved = self.get_unresolved_foreshadowings()
        # 筛选当前章附近（±3章）的伏笔
        current_ch = outline.chapter_number
        relevant_fs = [
            f
            for f in unresolved
            if abs(f.plant_chapter - current_ch) <= 3
        ]

        return AssembledContext(
            current_outline=outline,
            character_states=dict(self._character_states),
            recent_summaries=list(self._chapter_summaries),
            unresolved_foreshadowing=relevant_fs,
            style_notes=style_notes,
            world_rules=world_rules or [],
        )

    def generate_context_text(self, ctx: AssembledContext) -> str:
        """将 AssembledContext 转为 LLM 可读的纯文本上下文.

        这是传入 WriterAgent system prompt 的上下文文本。
        """
        parts: list[str] = []

        # 世界规则
        if ctx.world_rules:
            parts.append("【世界规则】")
            for rule in ctx.world_rules:
                parts.append(f"- {rule}")
            parts.append("")

        # 风格约束
        if ctx.style_notes:
            parts.append(f"【风格要求】{ctx.style_notes}")
            parts.append("")

        # 当前章目标
        if ctx.current_outline:
            o = ctx.current_outline
            parts.append(f"【本章目标】第{o.chapter_number}章 {o.title}")
            if o.milestone_events:
                parts.append("路标事件：")
                for event in o.milestone_events:
                    parts.append(f"  - {event}")
            if o.goals:
                parts.append("叙事目标：")
                for goal in o.goals:
                    parts.append(f"  - {goal}")
            if o.conflicts:
                parts.append("冲突设置：")
                for conflict in o.conflicts:
                    parts.append(f"  - {conflict}")
            if o.hook:
                parts.append(f"章末钩子：{o.hook}")
            parts.append("")

        # 角色状态
        if ctx.character_states:
            parts.append("【角色当前状态】")
            for name, state in ctx.character_states.items():
                parts.append(f"- {state}")
            parts.append("")

        # 最近章节摘要
        if ctx.recent_summaries:
            parts.append("【前情提要】")
            for summary in ctx.recent_summaries:
                parts.append(f"第{summary.chapter_number}章 {summary.title}：{summary.summary}")
            parts.append("")

        # 未回收伏笔
        if ctx.unresolved_foreshadowing:
            parts.append("【待回收伏笔】")
            for fs in ctx.unresolved_foreshadowing:
                parts.append(f"- [{fs.id}] (第{fs.plant_chapter}章埋设) {fs.description}")
            parts.append("")

        return "\n".join(parts)
