"""ArchitectAgent — 将章节大纲展开为可执行的写作简报."""

from __future__ import annotations

from momashuju.config import Config
from momashuju.llm.client import LLMClient
from momashuju.llm.prompts.architect import ARCHITECT_SYSTEM_PROMPT
from momashuju.runtime.context import AssembledContext, ContextManager


class ArchitectAgent:
    """大纲 → 写作简报.

    使用 LLM 将高层次的章节大纲展开为包含场景拆分、节奏控制、
    角色情感节拍和具体细节的写作简报。
    """

    def __init__(self, llm: LLMClient, config: Config) -> None:
        self._llm = llm
        agent_config = config.get("llm.agents.architect", {})
        self._model = agent_config.get("model")
        self._temperature = agent_config.get("temperature")
        self._max_tokens = agent_config.get("max_tokens", 4096)

    def plan_chapter(self, context: AssembledContext) -> str:
        """将写作上下文展开为写作简报.

        Args:
            context: AssembledContext（由 ContextManager.assemble_context 产出）

        Returns:
            写作简报纯文本
        """
        # 使用 ContextManager 的文本生成方法获取上下文
        ctx_mgr = ContextManager()
        context_text = ctx_mgr.generate_context_text(context)

        user_message = f"""请根据以下创作上下文，为本章撰写写作简报。

{context_text}

请按照场景拆分、关键节奏、角色情感节拍、必须出现的细节、写作建议五个部分输出。
"""

        response = self._llm.chat(
            messages=[{"role": "user", "content": user_message}],
            system=ARCHITECT_SYSTEM_PROMPT,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        return response
