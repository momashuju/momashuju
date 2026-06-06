"""测试 Spec 层数据模型."""

import pytest
from momashuju.spec.models import (
    ChapterContent,
    ChapterOutline,
    Character,
    Foreshadowing,
    ForeshadowingStatus,
    ForeshadowingTracker,
    LanguageStyle,
    POV,
    Relationship,
    StyleConstraints,
    Tense,
    WorldSetting,
)


class TestWorldSetting:
    def test_minimal(self):
        w = WorldSetting(name="测试世界")
        assert w.name == "测试世界"
        assert w.era == ""
        assert w.factions == []

    def test_full(self):
        w = WorldSetting(
            name="艾尔德兰",
            era="中世纪",
            genre="西幻/异世界/高魔",
            magic_system="魔力存在于万物",
            factions=["人类王国", "龙族"],
            rules=["龙族可化人形"],
        )
        assert len(w.factions) == 2
        assert "龙族" in w.factions

    def test_yaml_roundtrip(self):
        """验证可序列化到 JSON（进而可写入 YAML）."""
        w = WorldSetting(
            name="测试",
            era="中世纪",
            factions=["人类", "精灵"],
        )
        data = w.model_dump()
        w2 = WorldSetting(**data)
        assert w2.name == w.name
        assert w2.factions == w.factions


class TestCharacter:
    def test_minimal(self):
        c = Character(name="测试角色")
        assert c.name == "测试角色"
        assert c.relationships == []
        assert c.abilities == []

    def test_with_relationships(self):
        c = Character(
            name="巫劫",
            role="主角",
            relationships=[
                Relationship(
                    target="琪莎拉",
                    relation="救命恩人",
                    attitude="positive",
                )
            ],
        )
        assert len(c.relationships) == 1
        assert c.relationships[0].target == "琪莎拉"
        assert c.relationships[0].attitude == "positive"

    def test_json_schema(self):
        """验证模型可导出 JSON Schema."""
        schema = Character.model_json_schema()
        assert schema["title"] == "角色档案"
        assert "name" in schema["properties"]
        assert "relationships" in schema["properties"]


class TestChapterOutline:
    def test_basic(self):
        ch = ChapterOutline(
            chapter_number=1,
            title="开始",
            estimated_words=3000,
        )
        assert ch.chapter_number == 1
        assert ch.estimated_words == 3000

    def test_chapter_number_min(self):
        with pytest.raises(Exception):
            ChapterOutline(chapter_number=0)  # 必须 >= 1


class TestStyleConstraints:
    def test_defaults(self):
        s = StyleConstraints()
        assert s.pov == POV.THIRD_LIMITED
        assert s.tense == Tense.PAST
        assert s.language_style == LanguageStyle.WEB_NOVEL

    def test_custom(self):
        s = StyleConstraints(
            pov=POV.FIRST,
            language_style=LanguageStyle.LITERARY,
            banned_words=["震撼", "恐怖如斯"],
        )
        assert s.pov == POV.FIRST
        assert len(s.banned_words) == 2


class TestForeshadowingTracker:
    def test_plant_and_resolve(self):
        tracker = ForeshadowingTracker()
        fs = Foreshadowing(
            id="fs_001",
            description="琪莎拉是龙族",
            plant_chapter=1,
        )
        tracker.plant(fs)
        assert len(tracker.planted) == 1
        assert len(tracker.resolved) == 0

        tracker.resolve("fs_001", pay_chapter=3)
        assert len(tracker.planted) == 0
        assert len(tracker.resolved) == 1

    def test_resolve_nonexistent(self):
        tracker = ForeshadowingTracker()
        with pytest.raises(ValueError, match="不存在"):
            tracker.resolve("nonexistent", 5)

    def test_get_unresolved_in_range(self):
        tracker = ForeshadowingTracker()
        tracker.plant(Foreshadowing(id="fs1", description="A", plant_chapter=1))
        tracker.plant(Foreshadowing(id="fs2", description="B", plant_chapter=3))
        tracker.plant(Foreshadowing(id="fs3", description="C", plant_chapter=5))

        unresolved = tracker.get_unresolved_in_range(1, 3)
        assert len(unresolved) == 2

    def test_abandoned(self):
        tracker = ForeshadowingTracker()
        fs = Foreshadowing(id="fs_x", description="废弃的", plant_chapter=1, status=ForeshadowingStatus.ABANDONED)
        tracker.plant(fs)
        assert len(tracker.abandoned) == 1
        assert len(tracker.planted) == 0


class TestChapterContent:
    def test_basic(self):
        cc = ChapterContent(
            chapter_number=1,
            title="第一章",
            content="这是正文内容。",
            word_count=7,
        )
        data = cc.model_dump()
        assert data["chapter_number"] == 1
        assert data["content"] == "这是正文内容。"
