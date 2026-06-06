"""LLM 客户端抽象层 — 当前实现 Claude (anthropic SDK)，预留多供应商扩展."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import anthropic

from momashuju.config import Config


class LLMClient(ABC):
    """LLM 客户端抽象基类."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """发送对话请求，返回文本响应."""
        ...

    @abstractmethod
    def chat_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """发送对话请求，返回符合 JSON Schema 的结构化输出."""
        ...


class ClaudeClient(LLMClient):
    """Claude API 客户端（anthropic SDK）."""

    def __init__(
        self,
        config: Config,
        *,
        api_key: str | None = None,
    ) -> None:
        llm_config = config.llm
        self._model = llm_config.get("model", "claude-sonnet-4-6")
        self._default_max_tokens = llm_config.get("max_tokens", 8192)
        self._default_temperature = llm_config.get("temperature", 0.7)
        self._client = anthropic.Anthropic(api_key=api_key)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        response = self._client.messages.create(
            model=self._model,
            system=system or "",
            messages=self._to_claude_messages(messages),
            max_tokens=max_tokens or self._default_max_tokens,
            temperature=temperature or self._default_temperature,
        )
        # 提取文本内容
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def chat_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """使用 Claude Tool Use 实现结构化输出.

        在 schema 上包装一层 tool_use，强制模型输出符合 JSON Schema 的数据。
        """
        tool_name = schema.get("title", "output").lower().replace(" ", "_")

        response = self._client.messages.create(
            model=self._model,
            system=system or "",
            messages=self._to_claude_messages(messages),
            max_tokens=max_tokens or self._default_max_tokens,
            temperature=temperature or self._default_temperature,
            tools=[
                {
                    "name": tool_name,
                    "description": schema.get("description", f"输出 {tool_name}"),
                    "input_schema": {
                        "type": "object",
                        "properties": schema.get("properties", {}),
                        "required": schema.get("required", []),
                    },
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
        )

        # 提取 tool_use 输入
        for block in response.content:
            if block.type == "tool_use":
                return block.input

        # Fallback：尝试从文本中解析 JSON
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        return {}

    @staticmethod
    def _to_claude_messages(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        """将通用格式转为 Claude API 格式.

        通用格式: {"role": "user|assistant|system", "content": "..."}
        """
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                # system 消息在顶层处理，这里跳过
                continue
            result.append({"role": role, "content": msg.get("content", "")})
        return result


def create_client(config: Config, *, api_key: str | None = None) -> LLMClient:
    """工厂函数：根据配置创建 LLM 客户端."""
    provider = config.get("llm.provider", "claude")
    if provider == "claude":
        return ClaudeClient(config, api_key=api_key)
    # 未来扩展:
    # elif provider == "deepseek":
    #     return DeepSeekClient(config, api_key=api_key)
    # elif provider == "openai":
    #     return OpenAIClient(config, api_key=api_key)
    raise ValueError(f"不支持的 LLM 供应商: {provider}")
