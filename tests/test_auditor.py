"""测试 AuditorAgent — LLM 多维度质量审计."""

from __future__ import annotations

from typing import Any

import pytest
from momashuju.config import Config
from momashuju.llm.client import LLMClient
from momashuju.verify.auditor import AuditorAgent
from momashuju.spec.models import ChapterContent, ChapterOutline, Character


# ── Mock ──


class MockLLM(LLMClient):
    def __init__(self, response=None):
        self._response = response or {}
        self.calls = []

    def chat(self, messages, **kw):
        self.calls.append(("chat", messages, kw))
        return "mock"

    def chat_structured(self, messages, schema, **kw):
        self.calls.append(("structured", messages, schema, kw))
        return self._response


# ── Fixtures ──


@pytest.fixture
def config():
    return Config({
        "llm": {
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "agents": {"auditor": {"temperature": 0.3}},
        },
    })


@pytest.fixture
def sample_content():
    return ChapterContent(
        chapter_number=1,
        title="测试章",
        content="巫劫推开门，看见琪莎拉正蹲在院子里。",
        summary="测试摘要",
    )


@pytest.fixture
def sample_outline():
    return ChapterOutline(
        chapter_number=1,
        title="测试章",
        milestone_events=["事件A"],
        goals=["目标1"],
        conflicts=["冲突1"],
        hook="钩子",
    )


@pytest.fixture
def sample_characters():
    return [
        Character(
            name="巫劫",
            role="主角",
            personality="勇敢但迟钝",
            desire="平静生活",
            fear="失去重要的人",
            speech_style="温和",
        ),
        Character(
            name="琪莎拉",
            role="女主",
            personality="呆萌、天真",
            desire="留在巫劫身边",
            fear="被抛弃",
            speech_style="简短直白",
        ),
    ]


class TestAuditorAgent:
    def test_audit_returns_dimensions(self, config, sample_content, sample_outline, sample_characters):
        """验证审计返回 6 个维度."""
        mock = MockLLM({
            "dimensions": {
                "plot_consistency": {"score": 8, "issues": [], "suggestions": []},
                "character_consistency": {"score": 9, "issues": [], "suggestions": []},
                "pacing": {"score": 7, "issues": [], "suggestions": ["加快中段节奏"]},
                "foreshadowing": {"score": 8, "issues": [], "suggestions": []},
                "readability": {"score": 9, "issues": [], "suggestions": []},
                "outline_adherence": {"score": 10, "issues": [], "suggestions": []},
            },
            "overall_comment": "整体质量良好。",
        })
        agent = AuditorAgent(mock, config)

        result = agent.audit(sample_content, sample_outline, sample_characters)

        assert "dimensions" in result
        assert "overall_comment" in result
        assert len(result["dimensions"]) == 6
        assert result["overall_comment"] == "整体质量良好。"

    def test_audit_passes_context(self, config, sample_content, sample_outline, sample_characters):
        """验证审计调用包含了角色和大纲信息."""
        mock = MockLLM({
            "dimensions": {
                dim: {"score": 8, "issues": [], "suggestions": []}
                for dim in AuditorAgent.DIMENSIONS
            },
            "overall_comment": "ok",
        })
        agent = AuditorAgent(mock, config)

        agent.audit(sample_content, sample_outline, sample_characters, context_text="前情提要测试")

        call = mock.calls[0]
        user_msg = call[1][0]["content"]
        assert "巫劫" in user_msg
        assert "琪莎拉" in user_msg
        assert "事件A" in user_msg
        assert "前情提要测试" in user_msg

    def test_empty_result_on_failure(self, config, sample_content, sample_outline, sample_characters):
        """LLM 调用失败时返回空结果（降级处理）."""
        result = AuditorAgent._empty_result()
        assert "dimensions" in result
        for dim in AuditorAgent.DIMENSIONS:
            assert dim in result["dimensions"]
            assert result["dimensions"][dim]["score"] == 10
            assert result["dimensions"][dim]["issues"] == []
