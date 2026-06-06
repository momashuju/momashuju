"""Pipeline 编排器 — 串联 Architect → Writer → Verify → (Revise) → Persist 全流程."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from momashuju.config import Config
from momashuju.llm.client import LLMClient
from momashuju.runtime.agents.architect import ArchitectAgent
from momashuju.runtime.agents.reviser import ReviserAgent
from momashuju.runtime.agents.writer import WriterAgent
from momashuju.runtime.context import ChapterSummary, ContextManager
from momashuju.runtime.state import StateManager
from momashuju.spec.loader import NovelProject
from momashuju.spec.models import ChapterAuditResult, ChapterContent, Foreshadowing
from momashuju.verify.rules import RuleSet

logger = logging.getLogger(__name__)


@dataclass
class ChapterResult:
    """单章执行结果."""

    chapter_number: int
    content: ChapterContent
    audit: ChapterAuditResult
    brief: str = ""
    revisions: int = 0          # 修订次数
    succeeded: bool = True
    error: str | None = None


@dataclass
class PipelineResult:
    """Pipeline 执行结果."""

    novel_title: str = ""
    chapters: list[ChapterResult] = field(default_factory=list)
    total_chapters: int = 0
    completed: int = 0
    failed: int = 0
    total_revisions: int = 0

    @property
    def all_passed(self) -> bool:
        return self.failed == 0


class Pipeline:
    """Runtime 流水线编排器.

    每章的完整流程:
    1. ContextManager.assemble_context() → 写作上下文
    2. ArchitectAgent.plan_chapter()      → 写作简报
    3. WriterAgent.write_chapter()        → 章节正文
    4. ValidatorAgent.check_all()         → 审计结果
    5. (如果未通过) ReviserAgent.revise() → 修订, 回到步骤4
    6. ContextManager.update_after_chapter() → 更新状态
    7. StateManager.save_chapter()        → 持久化
    """

    MAX_REVISION_ROUNDS = 3

    def __init__(
        self,
        architect: ArchitectAgent,
        writer: WriterAgent,
        reviser: ReviserAgent,
        rule_set: RuleSet,
        context_mgr: ContextManager,
        state_mgr: StateManager,
        config: Config,
        *,
        # AuditorAgent 暂未实现，通过此参数注入（可选）
        auditor: Any = None,
    ) -> None:
        self._architect = architect
        self._writer = writer
        self._reviser = reviser
        self._rule_set = rule_set
        self._context_mgr = context_mgr
        self._state_mgr = state_mgr
        self._config = config
        self._auditor = auditor
        # 初始化评分计算器
        from momashuju.verify.scoring import ScoreCalculator
        self._scorer = ScoreCalculator(config)

    @classmethod
    def create_default(
        cls,
        llm: LLMClient,
        config: Config,
        *,
        output_dir: str | Path | None = None,
        with_auditor: bool = False,
    ) -> "Pipeline":
        """工厂方法：用默认组件创建 Pipeline.

        Args:
            llm: LLM 客户端
            config: 配置
            output_dir: 输出目录
            with_auditor: 是否启用 LLM 审计（会增加 API 调用成本）
        """
        from momashuju.verify.auditor import AuditorAgent
        from momashuju.verify.rules import RuleSet

        if output_dir is None:
            output_dir = config.get("paths.output_dir", "output")

        auditor = AuditorAgent(llm, config) if with_auditor else None

        return cls(
            architect=ArchitectAgent(llm, config),
            writer=WriterAgent(llm, config),
            reviser=ReviserAgent(llm, config),
            rule_set=RuleSet.create_default(config.rules),
            context_mgr=ContextManager(
                max_history=config.get("context.max_history_chapters", 3)
            ),
            state_mgr=StateManager(output_dir),
            config=config,
            auditor=auditor,
        )

    def run(
        self,
        project: NovelProject,
        *,
        start_chapter: int = 1,
        end_chapter: int | None = None,
    ) -> PipelineResult:
        """执行写作流水线.

        Args:
            project: NovelProject（已加载的 spec）
            start_chapter: 起始章节（1-based），用于断点续写
            end_chapter: 结束章节（1-based），None = 全部

        Returns:
            PipelineResult
        """
        chapters = project.chapters
        if not chapters:
            return PipelineResult(novel_title=project.title)

        if end_chapter is None:
            end_chapter = len(chapters)

        # 尝试恢复状态（断点续写）
        self._state_mgr.restore_context(self._context_mgr)

        result = PipelineResult(
            novel_title=project.title,
            total_chapters=end_chapter - start_chapter + 1,
        )

        style_notes = project.style.notes if project.style else ""
        world_rules = project.world.rules if project.world else []

        for i, outline in enumerate(chapters):
            ch_num = outline.chapter_number

            # 跳过已完成或未在范围内的章节
            if ch_num < start_chapter:
                continue
            if ch_num > end_chapter:
                break

            logger.info(f"=== Chapter {ch_num}: {outline.title} ===")

            chapter_result = self._run_chapter(
                outline=outline,
                characters=project.characters,
                style_notes=style_notes,
                world_rules=world_rules,
            )

            result.chapters.append(chapter_result)
            if chapter_result.succeeded:
                result.completed += 1
            else:
                result.failed += 1
            result.total_revisions += chapter_result.revisions

            # 如果当前章失败且修订超限，停止后续章节
            if not chapter_result.succeeded:
                logger.error(f"Chapter {ch_num} failed after {chapter_result.revisions} revisions. Stopping pipeline.")
                break

        return result

    def _run_chapter(
        self,
        outline,
        characters,
        style_notes: str,
        world_rules: list[str],
    ) -> ChapterResult:
        """执行单章的完整流程."""
        ch_num = outline.chapter_number

        try:
            # 1. 组装上下文
            context = self._context_mgr.assemble_context(
                outline=outline,
                characters=characters,
                style_notes=style_notes,
                world_rules=world_rules,
            )

            # 2. 架构师 → 写作简报
            logger.info(f"  Architect planning chapter {ch_num}...")
            brief = self._architect.plan_chapter(context)

            # 3. 写手 → 章节正文
            logger.info(f"  Writer writing chapter {ch_num}...")
            content = self._writer.write_chapter(brief, context)

            # 4. 验证
            logger.info(f"  Validator checking chapter {ch_num}...")
            audit = self._run_audit(content, outline=outline, characters=characters, context=context)
            revisions = 0

            # 5. 修订循环（最多 MAX_REVISION_ROUNDS 次）
            while not audit.passed and revisions < self.MAX_REVISION_ROUNDS:
                logger.info(f"  Reviser round {revisions + 1} for chapter {ch_num}...")
                content = self._reviser.revise(content, audit, brief, context)
                audit = self._run_audit(content, outline=outline, characters=characters, context=context)
                revisions += 1

            if not audit.passed:
                logger.warning(
                    f"  Chapter {ch_num} did not pass audit after {revisions} revisions."
                )
                return ChapterResult(
                    chapter_number=ch_num,
                    content=content,
                    audit=audit,
                    brief=brief,
                    revisions=revisions,
                    succeeded=False,
                    error=f"Audit not passed after {self.MAX_REVISION_ROUNDS} revision rounds",
                )

            # 6. 更新上下文状态
            self._context_mgr.update_after_chapter(
                ChapterSummary(
                    chapter_number=ch_num,
                    title=content.title,
                    summary=content.summary,
                    key_events=[],
                    character_changes=content.character_state_updates,
                    foreshadowing_updates=[
                        fs.get("id", "") if isinstance(fs, dict) else fs.id
                        for fs in content.foreshadowing_updates
                    ],
                )
            )

            # 注册新伏笔
            for fs_data in content.foreshadowing_updates:
                if isinstance(fs_data, dict):
                    if fs_data.get("status") == "planted":
                        self._context_mgr.register_foreshadowing(
                            Foreshadowing(**fs_data)
                        )
                elif hasattr(fs_data, "status") and fs_data.status == "planted":
                    self._context_mgr.register_foreshadowing(fs_data)

            # 7. 持久化
            self._state_mgr.save_chapter(content)
            self._state_mgr.save_project_state(
                context_mgr=self._context_mgr,
                novel_title=outline.title,
                current_chapter=ch_num,
                completed_chapters=[ch_num],
            )

            logger.info(f"  Chapter {ch_num} complete. score={audit.score:.2f}")
            return ChapterResult(
                chapter_number=ch_num,
                content=content,
                audit=audit,
                brief=brief,
                revisions=revisions,
                succeeded=True,
            )

        except Exception as e:
            logger.exception(f"  Chapter {ch_num} failed with error: {e}")
            return ChapterResult(
                chapter_number=ch_num,
                content=ChapterContent(chapter_number=ch_num, content=""),
                audit=ChapterAuditResult(chapter_number=ch_num, passed=False),
                succeeded=False,
                error=str(e),
            )

    def _run_audit(
        self,
        content: ChapterContent,
        *,
        outline=None,
        characters=None,
        context=None,
    ) -> ChapterAuditResult:
        """运行全部验证：确定性规则 + (可选的) LLM 审计 → 加权评分.

        Args:
            content: 章节内容
            outline: 本章大纲 (LLM 审计需要)
            characters: 角色列表 (LLM 审计需要)
            context: AssembledContext (LLM 审计需要)
        """
        # Layer 1: 确定性规则检查
        rule_results = self._rule_set.check_all(content.content)

        # Layer 2: LLM 审计（如果 auditor 可用）
        llm_audit = None
        if self._auditor and outline and characters:
            logger.info(f"  Auditor checking chapter {content.chapter_number}...")
            context_text = ""
            if context:
                from momashuju.runtime.context import ContextManager
                ctx_mgr = ContextManager()
                ctx_mgr._chapter_summaries = context.recent_summaries
                context_text = ctx_mgr.generate_context_text(context)
                # 只取前情提要和伏笔部分
                lines = context_text.split("\n")
                relevant_lines = []
                in_relevant = False
                for line in lines:
                    if line.startswith("【前情提要】") or line.startswith("【待回收伏笔】"):
                        in_relevant = True
                    elif line.startswith("【") and not line.startswith("【前情提要】") and not line.startswith("【待回收伏笔】"):
                        in_relevant = False
                    if in_relevant:
                        relevant_lines.append(line)
                context_text = "\n".join(relevant_lines)

            llm_audit = self._auditor.audit(
                content=content,
                outline=outline,
                characters=characters,
                context_text=context_text,
            )

        # 合并评分
        return self._scorer.calculate(
            chapter_number=content.chapter_number,
            rule_results=rule_results,
            llm_audit=llm_audit,
        )
