"""模板工厂 — 生成带注释的 YAML 模板，帮助用户快速创建 spec."""

from __future__ import annotations


def create_world_template() -> str:
    """生成世界观设定模板（YAML 格式 + 注释）."""
    return """\
# ═══════════════════════════════════════════════
# 世界观设定模板
# ═══════════════════════════════════════════════

# 世界观名称
name: ""

# 时代背景（如：中世纪、近未来、架空古代）
era: ""

# 类型标签（如：西幻/异世界/高魔、修仙/玄幻）
genre: ""

# 力量/魔法体系描述
magic_system: ""

# 地理环境概要
geography: ""

# 势力/阵营列表
factions:
  # - name: ""
  #   description: ""
  #   goal: ""

# 关键历史事件
history: ""

# 世界规则（物理/魔法限制等）
rules: []
  # - "规则1：..."

# 补充说明
notes: ""
"""


def create_character_template() -> str:
    """生成角色档案模板（YAML 格式 + 注释）."""
    return """\
# ═══════════════════════════════════════════════
# 角色档案模板
# 每个角色一个文件，或集中在 characters.yaml
# ═══════════════════════════════════════════════

characters:
  # ── 角色示例 ──
  # - name: ""
  #   aliases: []
  #   age: ""
  #   gender: ""
  #   role: "主角"           # 主角 / 女主 / 反派 / 配角

  #   # 外貌描述
  #   appearance: ""

  #   # 性格特征
  #   personality: ""

  #   # 核心欲望/目标
  #   desire: ""

  #   # 核心恐惧/弱点
  #   fear: ""

  #   # 能力/技能列表
  #   abilities: []

  #   # 关系网络
  #   relationships:
  #     - target: ""          # 关系对象
  #       relation: ""        # 关系类型（青梅竹马、战友、师徒…）
  #       description: ""     # 关系详述
  #       attitude: "neutral" # positive / negative / neutral / complicated

  #   # 知识边界（角色知道什么、不知道什么）
  #   knowledge_boundary: ""

  #   # 说话风格/口头禅
  #   speech_style: ""

  #   # 角色弧光/成长方向
  #   arc: ""

  #   # 补充说明
  #   notes: ""
"""


def create_outline_template() -> str:
    """生成章节大纲模板（YAML 格式 + 注释）."""
    return """\
# ═══════════════════════════════════════════════
# 章节大纲模板
# ═══════════════════════════════════════════════

chapters:
  # ── 第 1 章示例 ──
  # - chapter_number: 1
  #   title: ""
  #
  #   # 路标事件：本章必须发生的关键事件
  #   milestone_events:
  #     - ""
  #
  #   # 本章目标：需要达成的叙事目标
  #   goals:
  #     - ""
  #
  #   # 冲突设置：本章的矛盾与冲突
  #   conflicts:
  #     - ""
  #
  #   # 伏笔埋设：本章需要埋下的伏笔
  #   foreshadowing_plant:
  #     - ""
  #
  #   # 钩子：章末悬念
  #   hook: ""
  #
  #   # 视角角色
  #   pov_character: ""
  #
  #   # 预估字数
  #   estimated_words: 3000
"""


def create_novel_config_template() -> str:
    """生成小说项目配置模板."""
    return """\
# ═══════════════════════════════════════════════
# 小说项目配置
# ═══════════════════════════════════════════════

# 小说元信息
title: ""
author: ""
summary: ""
genre: ""

# LLM 配置覆盖（可选，不填则使用默认值）
# llm:
#   model: claude-sonnet-4-6
#   temperature: 0.8

# 写作风格约束
style:
  pov: third_limited           # first / third_limited / third_omniscient
  tense: past                  # past / present
  language_style: web_novel    # literary / web_novel / light_novel / realistic
  banned_words: []
  banned_patterns: []
  notes: ""

# 验证规则自定义（可选覆盖）
# rules:
#   custom_banned:
#     words: []
"""
