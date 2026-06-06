"""测试 Pipeline 编排器 — 端到端流程."""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from momashuju.config import Config
from momashuju.llm.client import LLMClient
from momashuju.runtime.agents.architect import ArchitectAgent
from momashuju.runtime.agents.reviser import ReviserAgent
from momashuju.runtime.agents.writer import WriterAgent
from momashuju.runtime.context import ContextManager
from momashuju.runtime.pipeline import ChapterResult, Pipeline, PipelineResult
from momashuju.runtime.state import StateManager
from momashuju.spec.loader import NovelProject
from momashuju.spec.models import (
    ChapterAuditResult,
    ChapterContent,
    ChapterOutline,
    Character,
    StyleConstraints,
    WorldSetting,
)
from momashuju.verify.rules import RuleSet


# ── Mocks ──


class MockLLM(LLMClient):
    """可编程的模拟 LLM."""

    def __init__(self, chat_fn=None, structured_fn=None):
        self._chat_fn = chat_fn or (lambda *a, **kw: "mock brief")
        self._structured_fn = structured_fn or (lambda *a, **kw: {
            "chapter_number": 1,
            "title": "mock",
            "content": "mock content",
            "word_count": 2,
            "summary": "mock summary",
            "character_state_updates": {},
            "foreshadowing_updates": [],
            "notes": "",
        })
        self.call_count = 0

    def chat(self, messages, *, system=None, max_tokens=None, temperature=None):
        self.call_count += 1
        return self._chat_fn(messages, system, max_tokens, temperature)

    def chat_structured(self, messages, schema, *, system=None, max_tokens=None, temperature=None):
        self.call_count += 1
        return self._structured_fn(messages, schema, system, max_tokens, temperature)


def make_sample_project():
    """构建 minimal NovelProject."""
    return NovelProject(
        title="测试小说",
        world=WorldSetting(name="测试世界", rules=["规则1"]),
        characters=[
            Character(name="主角", personality="勇敢", appearance="高大", desire="冒险"),
        ],
        chapters=[
            ChapterOutline(
                chapter_number=1,
                title="第一章",
                milestone_events=["事件1"],
                goals=["目标1"],
                conflicts=["冲突1"],
                hook="钩子1",
            ),
            ChapterOutline(
                chapter_number=2,
                title="第二章",
                milestone_events=["事件2"],
                goals=["目标2"],
                conflicts=["冲突2"],
                hook="钩子2",
            ),
        ],
        style=StyleConstraints(notes="测试风格"),
    )


def make_config():
    return Config({
        "llm": {
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "agents": {
                "architect": {"temperature": 0.8},
                "writer": {"temperature": 0.9},
                "reviser": {"temperature": 0.6},
            },
        },
        "context": {"max_history_chapters": 3},
        "rules": {
            "no_em_dash": {"enabled": True},
            "banned_patterns": {"enabled": False},
            "transition_density": {"enabled": False},
            "fatigue_words": {"enabled": False},
            "no_meta_narration": {"enabled": False},
            "no_report_terms": {"enabled": False},
            "no_author_preaching": {"enabled": False},
            "no_collective_reaction": {"enabled": False},
            "consecutive_le": {"enabled": False},
            "paragraph_length": {"enabled": False},
            "custom_banned": {"enabled": False},
        },
        "scoring": {
            "pass_threshold": 0.70,
            "weights": {
                "plot_consistency": 0.20,
                "character_consistency": 0.20,
                "pacing": 0.15,
                "foreshadowing": 0.15,
                "readability": 0.10,
                "outline_adherence": 0.10,
                "style_compliance": 0.10,
            },
        },
        "paths": {"output_dir": "output"},
    })


class TestPipeline:
    def test_run_single_chapter(self):
        """端到端：运行单章流水线."""
        config = make_config()
        mock_llm = MockLLM()
        project = make_sample_project()

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = Pipeline(
                architect=ArchitectAgent(mock_llm, config),
                writer=WriterAgent(mock_llm, config),
                reviser=ReviserAgent(mock_llm, config),
                rule_set=RuleSet.create_default(config.rules),
                context_mgr=ContextManager(max_history=3),
                state_mgr=StateManager(tmpdir),
                config=config,
            )

            result = pipeline.run(project, start_chapter=1, end_chapter=1)

            assert isinstance(result, PipelineResult)
            assert result.completed == 1
            assert result.failed == 0
            assert len(result.chapters) == 1
            assert result.chapters[0].succeeded
            assert result.chapters[0].content.content == "mock content"

    def test_run_multiple_chapters(self):
        """运行多章流水线."""
        config = make_config()
        mock_llm = MockLLM()
        project = make_sample_project()

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = Pipeline(
                architect=ArchitectAgent(mock_llm, config),
                writer=WriterAgent(mock_llm, config),
                reviser=ReviserAgent(mock_llm, config),
                rule_set=RuleSet.create_default(config.rules),
                context_mgr=ContextManager(max_history=3),
                state_mgr=StateManager(tmpdir),
                config=config,
            )

            result = pipeline.run(project, start_chapter=1)

            assert result.completed == 2
            assert result.failed == 0
            assert len(result.chapters) == 2
            # 验证 LLM 被调用了（Architect + Writer = 2 per chapter）
            assert mock_llm.call_count >= 4  # 2 chapters × (architect + writer)

    def test_revision_on_failure(self):
        """验证章节写完后如果审计不过会触发修订."""
        config = make_config()
        # 提高阈值，使得 em-dash 失败能触发修订
        config._data["scoring"]["pass_threshold"] = 0.95
        project = make_sample_project()

        # 先返回带破折号的内容（会触犯 no_em_dash 规则），第二次返回干净内容
        call_count = [0]

        def structured_fn(messages, schema, system, max_tokens, temperature):
            call_count[0] += 1
            if call_count[0] == 1:
                # 第一次写 —— 带破折号（rule fails → score=0.9 < 0.95 → revision）
                return {
                    "chapter_number": 1,
                    "title": "test",
                    "content": "他说——但是——她没有回答——因为——",
                    "word_count": 20,
                    "summary": "摘要",
                    "character_state_updates": {},
                    "foreshadowing_updates": [],
                    "notes": "",
                }
            else:
                # 修订后 —— 干净
                return {
                    "chapter_number": 1,
                    "title": "test",
                    "content": "他说，但是她没有回答，因为。",
                    "word_count": 15,
                    "summary": "修订后摘要",
                    "character_state_updates": {},
                    "foreshadowing_updates": [],
                    "notes": "",
                }

        mock_llm = MockLLM(structured_fn=structured_fn)

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = Pipeline(
                architect=ArchitectAgent(mock_llm, config),
                writer=WriterAgent(mock_llm, config),
                reviser=ReviserAgent(mock_llm, config),
                rule_set=RuleSet.create_default(config.rules),
                context_mgr=ContextManager(max_history=3),
                state_mgr=StateManager(tmpdir),
                config=config,
            )

            result = pipeline.run(project, start_chapter=1, end_chapter=1)

            assert result.completed == 1
            assert result.failed == 0
            # 应该有修订记录
            assert result.total_revisions >= 1
            # 修订后的内容不应该包含破折号
            final_content = result.chapters[0].content.content
            assert "——" not in final_content

    def test_max_revisions_exceeded(self):
        """验证修订超限后标记失败."""
        config = make_config()
        # 提高阈值，确保 em-dash 失败无法通过
        config._data["scoring"]["pass_threshold"] = 0.95
        project = make_sample_project()

        # 永远返回带破折号的内容
        def structured_fn(messages, schema, system, max_tokens, temperature):
            return {
                "chapter_number": 1,
                "title": "test",
                "content": "他说——但是——",
                "word_count": 5,
                "summary": "摘要",
                "character_state_updates": {},
                "foreshadowing_updates": [],
                "notes": "",
            }

        mock_llm = MockLLM(structured_fn=structured_fn)

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = Pipeline(
                architect=ArchitectAgent(mock_llm, config),
                writer=WriterAgent(mock_llm, config),
                reviser=ReviserAgent(mock_llm, config),
                rule_set=RuleSet.create_default(config.rules),
                context_mgr=ContextManager(max_history=3),
                state_mgr=StateManager(tmpdir),
                config=config,
            )

            result = pipeline.run(project, start_chapter=1, end_chapter=1)

            # 应该失败
            assert result.completed == 0
            assert result.failed == 1
            assert not result.chapters[0].succeeded
            assert result.chapters[0].revisions == Pipeline.MAX_REVISION_ROUNDS

    def test_resume_from_chapter(self):
        """验证 start_chapter 跳过已完成章节."""
        config = make_config()
        mock_llm = MockLLM()
        project = make_sample_project()

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = Pipeline(
                architect=ArchitectAgent(mock_llm, config),
                writer=WriterAgent(mock_llm, config),
                reviser=ReviserAgent(mock_llm, config),
                rule_set=RuleSet.create_default(config.rules),
                context_mgr=ContextManager(max_history=3),
                state_mgr=StateManager(tmpdir),
                config=config,
            )

            result = pipeline.run(project, start_chapter=2)

            # 只跑了第2章
            assert len(result.chapters) == 1
            assert result.chapters[0].chapter_number == 2


class TestPipelineResult:
    def test_all_passed(self):
        pr = PipelineResult(completed=2, failed=0)
        assert pr.all_passed

    def test_not_all_passed(self):
        pr = PipelineResult(completed=1, failed=1)
        assert not pr.all_passed
