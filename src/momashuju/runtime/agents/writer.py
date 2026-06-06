"""WriterAgent — 写作简报 + 上下文 → 章节正文."""

from __future__ import annotations

from momashuju.config import Config
from momashuju.llm.client import LLMClient
from momashuju.llm.prompts.writer import WRITER_SYSTEM_PROMPT
from momashuju.runtime.context import AssembledContext, ContextManager
from momashuju.spec.models import ChapterContent


class WriterAgent:
    """写作简报 → 章节正文.

    使用 LLM 根据写作简报和创作上下文撰写完整的章节内容，
    通过结构化输出同时产出正文和元数据（摘要、角色更新、伏笔更新）。
    """

    # Structured output schema — 复用 ChapterContent 的 JSON Schema
    OUTPUT_SCHEMA = {
        "title": "chapter_content",
        "description": "章节正文及元数据",
        "properties": {
            "chapter_number": {"type": "integer", "description": "章节序号"},
            "title": {"type": "string", "description": "章节标题"},
            "content": {"type": "string", "description": "章节正文，用空行分隔段落"},
            "word_count": {"type": "integer", "description": "正文字数"},
            "summary": {"type": "string", "description": "200字以内的本章摘要"},
            "character_state_updates": {
                "type": "object",
                "description": "角色名 → 本章结束时的状态变化描述",
                "additionalProperties": {"type": "string"},
            },
            "foreshadowing_updates": {
                "type": "array",
                "description": "本章的伏笔更新",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "伏笔ID（新埋的用新ID，回收的用已有ID）"},
                        "description": {"type": "string"},
                        "plant_chapter": {"type": "integer"},
                        "pay_chapter": {"type": "integer", "description": "回收章节，未回收则填null"},
                        "status": {"type": "string", "enum": ["planted", "partial", "resolved"]},
                        "related_characters": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "notes": {"type": "string", "description": "给下一章写手的备注"},
        },
        "required": ["chapter_number", "content", "summary"],
    }

    def __init__(self, llm: LLMClient, config: Config) -> None:
        self._llm = llm
        agent_config = config.get("llm.agents.writer", {})
        self._model = agent_config.get("model")
        self._temperature = agent_config.get("temperature")
        self._max_tokens = agent_config.get("max_tokens", 16384)

    def write_chapter(
        self,
        brief: str,
        context: AssembledContext,
    ) -> ChapterContent:
        """根据简报和上下文撰写章节.

        Args:
            brief: ArchitectAgent 产出的写作简报
            context: 完整写作上下文

        Returns:
            ChapterContent（正文 + 元数据）
        """
        ctx_mgr = ContextManager()
        context_text = ctx_mgr.generate_context_text(context)

        chapter_num = context.current_outline.chapter_number if context.current_outline else 0

        user_message = f"""## 写作简报

{brief}

## 创作上下文

{context_text}

---

请根据以上简报和上下文，撰写第{chapter_num}章的完整正文。
控制在 {context.current_outline.estimated_words if context.current_outline else 3000} 字左右。
"""

        result = self._llm.chat_structured(
            messages=[{"role": "user", "content": user_message}],
            schema=self.OUTPUT_SCHEMA,
            system=WRITER_SYSTEM_PROMPT,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )

        # 将结构化结果转为 ChapterContent
        return ChapterContent(
            chapter_number=result.get("chapter_number", chapter_num),
            title=result.get("title", ""),
            content=result.get("content", ""),
            word_count=result.get("word_count", 0),
            summary=result.get("summary", ""),
            character_state_updates=result.get("character_state_updates", {}),
            foreshadowing_updates=result.get("foreshadowing_updates", []),
            notes=result.get("notes", ""),
        )
