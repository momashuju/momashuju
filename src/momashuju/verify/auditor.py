"""AuditorAgent — LLM 多维度质量审计.

对已完成的章节进行 6 个维度的深度质量评估，
输出结构化评分 + 问题列表 + 修改建议。
"""

from __future__ import annotations

import logging
from typing import Any

from momashuju.config import Config
from momashuju.llm.client import LLMClient
from momashuju.llm.prompts.auditor import AUDITOR_OUTPUT_SCHEMA, AUDITOR_SYSTEM_PROMPT
from momashuju.spec.models import ChapterContent, ChapterOutline, Character

logger = logging.getLogger(__name__)


class AuditorAgent:
    """LLM 质量审计器.

    对章节进行多维度质量评估，作为验证层的第二道防线
    （第一道是确定性规则检查）。
    """

    # 维度名称列表（与 defaults.yaml 对齐）
    DIMENSIONS = [
        "plot_consistency",
        "character_consistency",
        "pacing",
        "foreshadowing",
        "readability",
        "outline_adherence",
    ]

    def __init__(self, llm: LLMClient, config: Config) -> None:
        self._llm = llm
        agent_config = config.get("llm.agents.auditor", {})
        self._model = agent_config.get("model")
        self._temperature = agent_config.get("temperature", 0.3)
        self._max_tokens = agent_config.get("max_tokens", 4096)

    def audit(
        self,
        content: ChapterContent,
        outline: ChapterOutline,
        characters: list[Character],
        *,
        context_text: str = "",
    ) -> dict[str, Any]:
        """对章节进行多维度质量审计.

        Args:
            content: 已写章节
            outline: 本章大纲
            characters: 角色列表
            context_text: 前情提要 + 伏笔清单等上下文

        Returns:
            dict: 结构化审计结果，包含 dimensions 和 overall_comment
                  如果 LLM 调用失败，返回空结果（降级处理）
        """
        # 构造角色摘要
        char_summaries = []
        for c in characters:
            parts = [f"{c.name}（{c.role}）"]
            if c.personality:
                parts.append(f"性格：{c.personality}")
            if c.desire:
                parts.append(f"欲望：{c.desire}")
            if c.fear:
                parts.append(f"恐惧：{c.fear}")
            if c.speech_style:
                parts.append(f"说话风格：{c.speech_style}")
            if c.knowledge_boundary:
                parts.append(f"知识边界：{c.knowledge_boundary}")
            char_summaries.append("；".join(parts))

        # 构造大纲摘要
        outline_parts = [f"第{outline.chapter_number}章：{outline.title}"]
        if outline.milestone_events:
            outline_parts.append("路标事件：" + "、".join(outline.milestone_events))
        if outline.goals:
            outline_parts.append("本章目标：" + "、".join(outline.goals))
        if outline.conflicts:
            outline_parts.append("冲突设置：" + "、".join(outline.conflicts))
        if outline.hook:
            outline_parts.append(f"章末钩子：{outline.hook}")
        outline_text = "\n".join(outline_parts)

        # 构造审计请求
        user_message = f"""## 章节大纲

{outline_text}

## 角色设定

{chr(10).join(char_summaries)}

## 前情提要

{context_text if context_text else "（第一章，无前情）"}

## 正文

{content.content}

---

请对以上章节进行多维度质量审计。每个维度给出 0-10 的评分，列出发现的问题和修改建议。
"""

        try:
            result = self._llm.chat_structured(
                messages=[{"role": "user", "content": user_message}],
                schema=AUDITOR_OUTPUT_SCHEMA,
                system=AUDITOR_SYSTEM_PROMPT,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
            )
            return result

        except Exception as e:
            logger.warning(f"AuditorAgent LLM call failed: {e}. Falling back to empty audit.")
            return self._empty_result()

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        """返回空的审计结果（LLM 调用失败时的降级处理）."""
        return {
            "dimensions": {
                dim: {"score": 10, "issues": [], "suggestions": []}
                for dim in AuditorAgent.DIMENSIONS
            },
            "overall_comment": "LLM 审计不可用，跳过。",
        }
