"""Runtime 层 — Agent 流水线 (Architect / Writer / Reviser) + Pipeline 编排."""

from momashuju.runtime.agents.architect import ArchitectAgent
from momashuju.runtime.agents.reviser import ReviserAgent
from momashuju.runtime.agents.writer import WriterAgent
from momashuju.runtime.context import (
    AssembledContext,
    ChapterSummary,
    ContextManager,
)
from momashuju.runtime.pipeline import ChapterResult, Pipeline, PipelineResult
from momashuju.runtime.state import ProjectState, StateManager

__all__ = [
    # agents
    "ArchitectAgent",
    "WriterAgent",
    "ReviserAgent",
    # context
    "ContextManager",
    "AssembledContext",
    "ChapterSummary",
    # pipeline
    "Pipeline",
    "PipelineResult",
    "ChapterResult",
    # state
    "StateManager",
    "ProjectState",
]
