"""ReviserAgent — 根据审计反馈定向修订章节."""

from __future__ import annotations

from momashuju.config import Config
from momashuju.llm.client import LLMClient
from momashuju.llm.prompts.reviser import REVISER_SYSTEM_PROMPT
from momashuju.runtime.context import AssembledContext
from momashuju.spec.models import ChapterAuditResult, ChapterContent


class ReviserAgent:
    """审计反馈 → 定向修订.

    根据审计结果中列出的问题，使用 LLM 对章节进行定向修改。
    如果审计全部通过，直接返回原章节（零 LLM 调用）。
    """

    # 复用与 WriterAgent 相同的输出 schema
    OUTPUT_SCHEMA = {
        "title": "chapter_content",
        "description": "修订后的章节正文及元数据",
        "properties": {
            "chapter_number": {"type": "integer"},
            "title": {"type": "string"},
            "content": {"type": "string", "description": "修订后的正文"},
            "word_count": {"type": "integer"},
            "summary": {"type": "string"},
            "character_state_updates": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
            "foreshadowing_updates": {
                "type": "array",
                "items": {"type": "object"},
            },
            "notes": {"type": "string"},
        },
        "required": ["chapter_number", "content", "summary"],
    }

    def __init__(self, llm: LLMClient, config: Config) -> None:
        self._llm = llm
        agent_config = config.get("llm.agents.reviser", {})
        self._model = agent_config.get("model")
        self._temperature = agent_config.get("temperature", 0.6)
        self._max_tokens = agent_config.get("max_tokens", 16384)

    def revise(
        self,
        chapter: ChapterContent,
        audit: ChapterAuditResult,
        brief: str = "",
        context: AssembledContext | None = None,
    ) -> ChapterContent:
        """根据审计反馈修订章节.

        如果审计全部通过（audit.passed == True），直接返回原章节。

        Args:
            chapter: 已写章节
            audit: 审计结果
            brief: 原始写作简报（可选，用于保持意图一致）
            context: 原始写作上下文（可选）

        Returns:
            修订后的 ChapterContent（或原章节，如果无需修订）
        """
        # 全部通过 → 跳过
        if audit.passed:
            return chapter

        # 构造修改指令
        issues_text = self._format_issues(audit)

        chapter_text = f"""## 原文

{chapter.content}

## 审计发现的问题

{issues_text}

## 原始写作简报

{brief if brief else "（无）"}

---

请对原文进行定向修订。只修改审计中指出的问题，不要改动通过的部分。
保持与原文一致的文风，避免出现拼接感。
"""

        result = self._llm.chat_structured(
            messages=[{"role": "user", "content": chapter_text}],
            schema=self.OUTPUT_SCHEMA,
            system=REVISER_SYSTEM_PROMPT,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )

        return ChapterContent(
            chapter_number=result.get("chapter_number", chapter.chapter_number),
            title=result.get("title", chapter.title),
            content=result.get("content", chapter.content),
            word_count=result.get("word_count", chapter.word_count),
            summary=result.get("summary", chapter.summary),
            character_state_updates=result.get("character_state_updates", chapter.character_state_updates),
            foreshadowing_updates=result.get("foreshadowing_updates", chapter.foreshadowing_updates),
            notes=result.get("notes", chapter.notes),
        )

    @staticmethod
    def _format_issues(audit: ChapterAuditResult) -> str:
        """将审计结果格式化为可读的问题列表."""
        lines: list[str] = []

        # 规则检查结果
        rule_failures = [r for r in audit.rule_results if not r.get("passed", True)]
        if rule_failures:
            lines.append("### 风格/格式问题")
            for i, r in enumerate(rule_failures, 1):
                lines.append(f"{i}. [{r.get('rule_name', 'unknown')}] {r.get('message', '')}")
            lines.append("")

        # LLM 审计结果
        llm_audit = audit.llm_audit
        if llm_audit:
            lines.append("### 内容质量问题")
            for key, value in llm_audit.items():
                if isinstance(value, list):
                    for item in value:
                        lines.append(f"- [{key}] {item}")
                elif value:
                    lines.append(f"- [{key}] {value}")
            lines.append("")

        # 综合问题和建议
        if audit.issues:
            lines.append("### 其他问题")
            for issue in audit.issues:
                lines.append(f"- {issue}")
            lines.append("")

        if audit.suggestions:
            lines.append("### 修改建议")
            for i, s in enumerate(audit.suggestions, 1):
                lines.append(f"{i}. {s}")

        if not lines:
            lines.append("无具体问题。")

        return "\n".join(lines)
