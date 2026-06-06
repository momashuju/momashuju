"""测试 StateManager — checkpoint 读写 + 断点恢复."""

import tempfile
from pathlib import Path

import pytest
from momashuju.runtime.context import ChapterSummary, ContextManager
from momashuju.runtime.state import ProjectState, StateManager
from momashuju.spec.models import (
    ChapterContent,
    Foreshadowing,
    ForeshadowingStatus,
)


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    # cleanup
    import shutil
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def state_mgr(temp_dir):
    return StateManager(temp_dir)


class TestStateManager:
    def test_save_and_load_chapter(self, state_mgr):
        content = ChapterContent(
            chapter_number=1,
            title="测试章",
            content="这是正文。",
            word_count=6,
            summary="摘要",
            character_state_updates={"角色A": "状态变化"},
            notes="备注",
        )

        path = state_mgr.save_chapter(content)
        assert path.exists()

        loaded = state_mgr.load_chapter(1)
        assert loaded is not None
        assert loaded.chapter_number == 1
        assert loaded.title == "测试章"
        assert loaded.content == "这是正文。"
        assert loaded.summary == "摘要"
        assert loaded.character_state_updates == {"角色A": "状态变化"}

    def test_load_nonexistent_chapter(self, state_mgr):
        loaded = state_mgr.load_chapter(99)
        assert loaded is None

    def test_save_and_load_project_state(self, state_mgr):
        ctx_mgr = ContextManager(max_history=3)
        ctx_mgr._character_states = {"角色A": "状态A"}
        ctx_mgr._chapter_summaries = [
            ChapterSummary(
                chapter_number=1,
                title="第一章",
                summary="摘要内容",
                key_events=["事件1"],
                character_changes={"角色A": "变化了"},
            )
        ]
        ctx_mgr._foreshadowings = [
            Foreshadowing(
                id="fs1",
                description="伏笔1",
                plant_chapter=1,
                status=ForeshadowingStatus.PLANTED,
            )
        ]

        path = state_mgr.save_project_state(
            ctx_mgr,
            novel_title="测试小说",
            current_chapter=1,
            completed_chapters=[1],
        )
        assert path.exists()

        # 加载
        loaded = state_mgr.load_project_state()
        assert loaded is not None
        assert loaded.novel_title == "测试小说"
        assert loaded.current_chapter == 1
        assert loaded.character_states == {"角色A": "状态A"}
        assert len(loaded.chapter_summaries) == 1
        assert loaded.chapter_summaries[0]["title"] == "第一章"
        assert loaded.completed_chapters == [1]

    def test_restore_context(self, state_mgr):
        # 先保存
        ctx_mgr = ContextManager()
        ctx_mgr._character_states = {"角色B": "状态B"}
        state_mgr.save_project_state(ctx_mgr, novel_title="test")

        # 创建新的 ContextManager 并恢复
        new_ctx = ContextManager()
        restored = state_mgr.restore_context(new_ctx)
        assert restored
        assert new_ctx._character_states == {"角色B": "状态B"}

    def test_restore_nonexistent(self, state_mgr):
        ctx_mgr = ContextManager()
        restored = state_mgr.restore_context(ctx_mgr)
        assert not restored

    def test_get_completed_chapters(self, state_mgr):
        # 保存几章
        for i in [1, 3, 5]:
            state_mgr.save_chapter(
                ChapterContent(chapter_number=i, content=f"第{i}章")
            )

        completed = state_mgr.get_completed_chapters()
        assert completed == [1, 3, 5]

    def test_get_next_chapter(self, state_mgr):
        # 保存第1章和第2章
        for i in [1, 2]:
            state_mgr.save_chapter(
                ChapterContent(chapter_number=i, content=f"第{i}章")
            )

        # 总共5章
        assert state_mgr.get_next_chapter(5) == 3

        # 全部完成
        for i in [3, 4, 5]:
            state_mgr.save_chapter(
                ChapterContent(chapter_number=i, content=f"第{i}章")
            )
        assert state_mgr.get_next_chapter(5) is None

    def test_yaml_roundtrip_encoding(self, state_mgr):
        """验证中文内容正确编码."""
        content = ChapterContent(
            chapter_number=1,
            content="中文内容：琪莎拉睁开了琥珀色的竖瞳。",
            summary="龙族少女的日常。",
        )
        state_mgr.save_chapter(content)
        loaded = state_mgr.load_chapter(1)
        assert loaded is not None
        assert "琪莎拉" in loaded.content
        assert "琥珀色" in loaded.content
