"""Spec 层数据模型 — Pydantic v2 定义.

所有模型支持：
- JSON Schema 导出（直接作为 LLM structured output schema）
- YAML 序列化/反序列化
- 字段校验
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints


# ── 枚举 ──


class ForeshadowingStatus(str, Enum):
    PLANTED = "planted"       # 已埋设
    PARTIAL = "partial"       # 部分回收
    RESOLVED = "resolved"     # 已回收
    ABANDONED = "abandoned"   # 已废弃


class POV(str, Enum):
    FIRST = "first"           # 第一人称
    THIRD_LIMITED = "third_limited"   # 第三人称有限视角
    THIRD_OMNISCIENT = "third_omniscient"  # 第三人称全知


class Tense(str, Enum):
    PAST = "past"
    PRESENT = "present"


class LanguageStyle(str, Enum):
    LITERARY = "literary"         # 文学性
    WEB_NOVEL = "web_novel"       # 网文风
    LIGHT_NOVEL = "light_novel"   # 轻小说
    REALISTIC = "realistic"       # 写实


# ── Spec 核心模型 ──


class WorldSetting(BaseModel):
    """世界观设定."""

    name: str = Field(default="", description="世界观名称")
    era: str = Field(default="", description="时代背景，如'中世纪'、'近未来'")
    genre: str = Field(default="", description="类型标签，如'西幻/异世界/高魔'")
    magic_system: str = Field(default="", description="力量/魔法体系描述")
    geography: str = Field(default="", description="地理环境概要")
    factions: list[str] = Field(default_factory=list, description="势力/阵营列表")
    history: str = Field(default="", description="关键历史事件")
    rules: list[str] = Field(default_factory=list, description="世界规则（物理/魔法限制等）")
    notes: str = Field(default="", description="补充说明")

    # Pydantic v2 配置
    model_config = {"json_schema_extra": {"title": "世界观设定"}}


class Relationship(BaseModel):
    """角色关系."""

    target: str = Field(..., description="关系对象名称")
    relation: str = Field(..., description="关系类型，如'青梅竹马'、'战友'")
    description: str = Field(default="", description="关系详述")
    attitude: str = Field(default="neutral", description="态度：positive/negative/neutral/complicated")


class Character(BaseModel):
    """角色档案."""

    # 基本信息
    name: str = Field(..., description="角色姓名")
    aliases: list[str] = Field(default_factory=list, description="别名/称号")
    age: str = Field(default="", description="年龄（可以是范围或相对描述）")
    gender: str = Field(default="", description="性别")
    role: str = Field(default="", description="角色定位，如'主角'、'女主'、'反派'")

    # 外在描述
    appearance: str = Field(default="", description="外貌描述")

    # 内在特质
    personality: str = Field(default="", description="性格特征")
    desire: str = Field(default="", description="核心欲望/目标")
    fear: str = Field(default="", description="核心恐惧/弱点")
    abilities: list[str] = Field(default_factory=list, description="能力/技能列表")

    # 叙事约束
    relationships: list[Relationship] = Field(default_factory=list, description="关系网络")
    knowledge_boundary: str = Field(
        default="",
        description="知识边界：角色知道什么、不知道什么，防止信息泄露",
    )
    speech_style: str = Field(default="", description="说话风格/口头禅")
    arc: str = Field(default="", description="角色弧光/成长方向")

    # 元数据
    notes: str = Field(default="", description="补充说明")

    model_config = {"json_schema_extra": {"title": "角色档案"}}


class ChapterOutline(BaseModel):
    """章节大纲."""

    chapter_number: int = Field(..., ge=1, description="章节序号")
    title: str = Field(default="", description="章节标题")
    milestone_events: list[str] = Field(
        default_factory=list,
        description="路标事件：本章必须发生的关键事件",
    )
    goals: list[str] = Field(
        default_factory=list,
        description="本章目标：本章需要达成的叙事目标",
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="冲突设置：本章中的矛盾与冲突",
    )
    foreshadowing_plant: list[str] = Field(
        default_factory=list,
        description="伏笔埋设：本章需要埋下的伏笔",
    )
    hook: str = Field(
        default="",
        description="钩子：章末悬念，驱动读者继续阅读",
    )
    pov_character: str = Field(default="", description="本章视角角色")
    estimated_words: int = Field(default=3000, ge=500, description="预估字数")

    model_config = {"json_schema_extra": {"title": "章节大纲"}}


class StyleConstraints(BaseModel):
    """写作风格约束."""

    pov: POV = Field(default=POV.THIRD_LIMITED, description="叙事视角")
    tense: Tense = Field(default=Tense.PAST, description="时态")
    language_style: LanguageStyle = Field(
        default=LanguageStyle.WEB_NOVEL, description="语言风格"
    )
    paragraph_max_chars: int = Field(default=300, description="段落最大字数")
    banned_words: list[str] = Field(default_factory=list, description="禁用词表")
    banned_patterns: list[str] = Field(
        default_factory=list,
        description="禁用句式（正则）",
    )
    required_elements: list[str] = Field(
        default_factory=list,
        description="每章必须包含的元素",
    )
    notes: str = Field(default="", description="补充风格说明")

    model_config = {"json_schema_extra": {"title": "写作风格约束"}}


class Foreshadowing(BaseModel):
    """单个伏笔."""

    id: str = Field(..., description="伏笔唯一标识")
    description: str = Field(..., description="伏笔描述")
    plant_chapter: int = Field(..., ge=1, description="埋设章节")
    pay_chapter: int | None = Field(default=None, ge=1, description="回收章节（未回收则为空）")
    status: ForeshadowingStatus = Field(default=ForeshadowingStatus.PLANTED, description="伏笔状态")
    related_characters: list[str] = Field(default_factory=list, description="相关角色")
    notes: str = Field(default="", description="备注")


class ForeshadowingTracker(BaseModel):
    """伏笔追踪器."""

    items: list[Foreshadowing] = Field(default_factory=list, description="伏笔列表")

    @property
    def planted(self) -> list[Foreshadowing]:
        return [f for f in self.items if f.status == ForeshadowingStatus.PLANTED]

    @property
    def resolved(self) -> list[Foreshadowing]:
        return [f for f in self.items if f.status == ForeshadowingStatus.RESOLVED]

    @property
    def abandoned(self) -> list[Foreshadowing]:
        return [f for f in self.items if f.status == ForeshadowingStatus.ABANDONED]

    def plant(self, foreshadowing: Foreshadowing) -> None:
        """添加新伏笔."""
        self.items.append(foreshadowing)

    def resolve(self, foreshadowing_id: str, pay_chapter: int) -> None:
        """标记伏笔已回收."""
        for f in self.items:
            if f.id == foreshadowing_id:
                f.status = ForeshadowingStatus.RESOLVED
                f.pay_chapter = pay_chapter
                return
        raise ValueError(f"伏笔 '{foreshadowing_id}' 不存在")

    def get_unresolved_in_range(self, start_chapter: int, end_chapter: int) -> list[Foreshadowing]:
        """获取指定章节范围内埋设但未回收的伏笔."""
        return [
            f
            for f in self.items
            if start_chapter <= f.plant_chapter <= end_chapter
            and f.status != ForeshadowingStatus.RESOLVED
        ]


# ── 章节输出模型 ──


class ChapterContent(BaseModel):
    """章节正文（WriterAgent 输出）."""

    chapter_number: int = Field(..., ge=1)
    title: str = Field(default="")
    content: str = Field(..., description="章节正文")
    word_count: int = Field(default=0, description="字数统计")
    summary: str = Field(default="", description="本章摘要（用于上下文压缩）")
    character_state_updates: dict[str, str] = Field(
        default_factory=dict,
        description="角色状态更新：角色名 → 状态摘要",
    )
    foreshadowing_updates: list[Foreshadowing] = Field(
        default_factory=list,
        description="本章伏笔更新",
    )
    notes: str = Field(default="", description="作者备注")


class ChapterAuditResult(BaseModel):
    """章节审计结果（Verify 层输出）."""

    chapter_number: int = Field(..., ge=1, description="章节序号")
    passed: bool = Field(..., description="是否通过审计")
    score: float = Field(default=0.0, ge=0.0, le=1.0, description="综合评分")
    rule_results: list[dict[str, Any]] = Field(
        default_factory=list, description="确定性规则检查结果"
    )
    llm_audit: dict[str, Any] = Field(default_factory=dict, description="LLM 审计结果")
    issues: list[str] = Field(default_factory=list, description="发现的问题")
    suggestions: list[str] = Field(default_factory=list, description="修改建议")
