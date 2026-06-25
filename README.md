# momashuju — AI 小说写作系统（Multica 原生版）

本仓库是 **momashuju** AI 小说写作系统的产物存储库，由 Multica 平台上的多 Agent 协作生成和管理。

---

## 仓库结构

```
momashuju/
└── novels/
    ├── outlines/              # 候选大纲草稿（spec 生成前的探索阶段产物）
    │   └── <框架名>.md
    └── <novel-name>/
        ├── spec.json          # 结构化设定（世界观、人设、卷级大纲、章节细纲）
        ├── state.json         # 写作进度（已完成章节、当前状态）
        └── chapters/
            ├── chapter_01.md
            ├── chapter_02.md
            └── ...
```

---

## 系统架构

本系统完全运行在 Multica 平台上，由以下角色协作完成小说创作：

| 角色 | 类型 | 职责 |
|---|---|---|
| PM Agent | Agent | 协调整体流程、拆解任务、汇总结果 |
| **Spec Agent** | **Agent** | **创意策划：探索世界观/人设/大纲方向，生成完整 spec.json** |
| Writer Agent | Agent | 根据 spec.json 生成章节正文 |
| Novel QA Agent | Agent | 对章节执行质量校验，输出通过/驳回+理由 |
| novel-spec | Skill | 将创意描述结构化为 spec.json 并提交到本仓库（Spec Agent 调用） |
| chapter-archive | Skill | 将通过 QA 的章节提交到本仓库，更新 state.json |

---

## 端到端工作流

```
【阶段一：创意策划】
用户向 PM 描述小说需求（Multica Issue）
  ↓
PM → Spec Agent
  ├─ 探索模式（方向未定）→ 生成候选大纲 → 用户选择方向
  └─ 规格模式（方向已定）→ 生成完整 spec.json（世界观+人设+卷纲+前3章细纲）提交仓库

【阶段二：章节写作（逐章循环）】
PM 创建「写第 N 章」子任务 → Writer Agent 生成章节草稿
  ↓
PM 创建「QA 第 N 章」子任务 → Novel QA Agent 校验
  ├─ 通过 → PM 调用 chapter-archive Skill 提交章节 → 通知用户
  └─ 驳回 → PM 创建「修改第 N 章」子任务 → Writer 修改 → 重新 QA
  ↓
用户确认后，继续下一章
```

**触发方式**：用户只需创建 Issue 并指派给 PM，整个流程由 PM 自动驱动。探索阶段有决策点（选择方向）需要用户回复；确定方向后流水线可以连续运行直到每章完成。

---

## spec.json 结构

Spec Agent 生成的 `spec.json` 包含以下维度，供 Writer 和 QA 使用：

| 字段 | 内容 |
|---|---|
| `title` / `summary` / `genre` | 基本信息和一句话概述 |
| `style` | 叙事视角、时态、语言风格、禁用词、必要元素 |
| `world` | 世界观、地理、势力、魔法体系、历史背景 |
| `characters` | 每个主要角色：外貌、性格、欲望、恐惧、能力、关系网、成长弧线 |
| `volumes` | 卷级结构：主线事件、冲突、情绪节点、结尾 |
| `chapters` | 前三章细纲：里程碑事件、目标、冲突、伏笔、钩子 |

---

## QA 验证规则

Novel QA Agent 分两层校验：

**第一层：结构性检查（客观）**
1. 字数是否在目标范围内
2. 章节是否有完整的开头、发展、结尾
3. 出场人物名称是否与 spec.json 一致

**第二层：叙事质量审计（LLM 评分）**
4. 情节连贯性：与前序章节是否矛盾
5. 人物一致性：角色行为/语言风格是否符合人设
6. 节奏感：场景推进是否自然，无冗余/跳跃
7. 内容新鲜度：是否重复已写内容
8. 目标推进度：本章是否有效推进了大纲中的情节目标

每条输出「通过 / 驳回 + 具体原因」。

---

## 如何开始

在 Multica 工作区中创建 Issue，指派给 PM Agent，描述你想写的小说即可。建议包含：题材/类型、主角和核心人物、大致情感基调。PM Agent 会自动驱动后续流程。
