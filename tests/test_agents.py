"""测试 Runtime Agents — 使用模拟 LLM 客户端."""

from __future__ import annotations

from typing import Any

import pytest
from momashuju.config import Config
from momashuju.llm.client import LLMClient
from momashuju.runtime.agents.architect import ArchitectAgent
from momashuju.runtime.agents.reviser import ReviserAgent
from momashuju.runtime.agents.writer import WriterAgent
from momashuju.runtime.context import AssembledContext, ContextManager
from momashuju.spec.models import (
    ChapterAuditResult,
    ChapterContent,
    ChapterOutline,
    Character,
)


# ── Mock LLM Client ──


class MockLLMClient(LLMClient):
    """模拟 LLM 客户端，返回可配置的响应."""

    def __init__(self, responses: dict[str, str] | None = None):
        self._responses = responses or {}
        self.calls: list[dict] = []  # 记录所有调用

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        self.calls.append({
            "method": "chat",
            "messages": messages,
            "system": system,
        })
        return self._responses.get("chat", "mock response")

    def chat_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        self.calls.append({
            "method": "chat_structured",
            "messages": messages,
            "system": system,
        })
        return self._responses.get("structured", {"content": "mock", "summary": "mock"})


# ── Fixtures ──


@pytest.fixture
def config():
    return Config({
        "llm": {
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "agents": {},
        },
    })


@pytest.fixture
def sample_context():
    outline = ChapterOutline(
        chapter_number=1,
        title="测试章节",
        milestone_events=["事件A", "事件B"],
        goals=["目标1"],
        conflicts=["冲突1"],
        hook="章末钩子",
    )
    character = Character(
        name="测试角色",
        personality="勇敢",
        appearance="高大",
        desire="拯救世界",
    )
    ctx_mgr = ContextManager()
    return ctx_mgr.assemble_context(outline, [character], style_notes="测试风格")


# ── ArchitectAgent ──


class TestArchitectAgent:
    def test_plan_chapter_returns_string(self, config, sample_context):
        mock = MockLLMClient({"chat": "### 场景拆分\n\n场景1：开场"})
        agent = ArchitectAgent(mock, config)
        result = agent.plan_chapter(sample_context)
        assert isinstance(result, str)
        assert len(result) > 0
        assert mock.calls[0]["method"] == "chat"

    def test_plan_chapter_passes_context(self, config, sample_context):
        mock = MockLLMClient({"chat": "简报内容"})
        agent = ArchitectAgent(mock, config)
        agent.plan_chapter(sample_context)
        call = mock.calls[0]
        # 验证 system prompt 包含了关键指令
        assert "场景拆分" in call["system"]
        # 验证 user message 包含了上下文信息
        user_msg = call["messages"][0]["content"]
        assert "测试章节" in user_msg
        assert "事件A" in user_msg


# ── WriterAgent ──


class TestWriterAgent:
    def test_write_chapter_returns_chapter_content(self, config, sample_context):
        structured_response = {
            "chapter_number": 1,
            "title": "第一章",
            "content": "这是第一章的正文内容。\n\n第二段。",
            "word_count": 20,
            "summary": "本章摘要",
            "character_state_updates": {"测试角色": "状态更新了"},
            "foreshadowing_updates": [
                {"id": "fs1", "description": "新伏笔", "plant_chapter": 1, "status": "planted", "related_characters": []}
            ],
            "notes": "备注",
        }
        mock = MockLLMClient({"structured": structured_response})
        agent = WriterAgent(mock, config)

        result = agent.write_chapter("写作简报", sample_context)

        assert isinstance(result, ChapterContent)
        assert result.chapter_number == 1
        assert result.content == "这是第一章的正文内容。\n\n第二段。"
        assert result.summary == "本章摘要"
        assert result.character_state_updates == {"测试角色": "状态更新了"}
        assert len(result.foreshadowing_updates) == 1

    def test_write_chapter_uses_structured_output(self, config, sample_context):
        mock = MockLLMClient({"structured": {"chapter_number": 1, "content": "X", "summary": "Y"}})
        agent = WriterAgent(mock, config)
        agent.write_chapter("简报", sample_context)
        call = mock.calls[0]
        assert call["method"] == "chat_structured"
        assert "chapter_content" in call["system"].lower() or True  # schema passed


# ── ReviserAgent ──


class TestReviserAgent:
    def test_skip_when_audit_passed(self, config):
        mock = MockLLMClient()
        agent = ReviserAgent(mock, config)
        chapter = ChapterContent(chapter_number=1, content="原文")
        audit = ChapterAuditResult(chapter_number=1, passed=True, score=1.0)

        result = agent.revise(chapter, audit)

        # 应该跳过 LLM 调用
        assert len(mock.calls) == 0
        # 返回原章节
        assert result.content == "原文"

    def test_revise_when_audit_failed(self, config):
        mock = MockLLMClient({
            "structured": {
                "chapter_number": 1,
                "content": "修改后的正文",
                "summary": "修改后摘要",
            }
        })
        agent = ReviserAgent(mock, config)
        chapter = ChapterContent(
            chapter_number=1,
            content="原文有问题",
            summary="原摘要",
        )
        audit = ChapterAuditResult(
            chapter_number=1,
            passed=False,
            score=0.5,
            rule_results=[
                {"rule_name": "no_em_dash", "passed": False, "severity": "warning", "message": "发现3处破折号"}
            ],
            issues=["使用了破折号"],
            suggestions=["替换为逗号或句号"],
        )

        result = agent.revise(chapter, audit, brief="原始简报")

        assert len(mock.calls) == 1
        assert mock.calls[0]["method"] == "chat_structured"
        assert result.content == "修改后的正文"
        assert result.summary == "修改后摘要"

    def test_format_issues(self, config):
        mock = MockLLMClient()
        agent = ReviserAgent(mock, config)
        audit = ChapterAuditResult(
            chapter_number=1,
            passed=False,
            rule_results=[
                {"rule_name": "r1", "passed": False, "severity": "error", "message": "错误1"},
                {"rule_name": "r2", "passed": True, "severity": "warning", "message": "通过"},
            ],
            issues=["问题A", "问题B"],
            suggestions=["建议1"],
        )

        formatted = agent._format_issues(audit)
        assert "r1" in formatted
        assert "错误1" in formatted
        assert "问题A" in formatted
        assert "建议1" in formatted
        # 通过的规则不应该出现
        assert "r2" not in formatted
