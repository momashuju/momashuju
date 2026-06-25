# momashuju — AI 小说写作系统（Multica 原生版）

本仓库是 **momashuju** AI 小说写作系统的产物存储库，由 Multica 平台上的多 Agent 协作生成和管理。

---

## 仓库结构

```
momashuju/
└── novels/
    └── <novel-name>/
        ├── spec.json          # 结构化设定（人物、世界观、大纲）
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
| Writer Agent | Agent | 根据 spec 生成章节正文 |
| Novel QA Agent | Agent | 对章节执行质量校验，输出通过/驳回+理由 |
| novel-spec | Skill | 将用户需求结构化为 spec.json 并提交到本仓库 |
| chapter-archive | Skill | 将通过 QA 的章节提交到本仓库，更新 state.json |

---

## 端到端工作流

```
用户描述小说需求（Multica Issue 评论）
  ↓
PM Agent → novel-spec Skill → 生成 spec.json 提交仓库
  ↓
PM Agent 创建「写第 N 章」子任务 → Writer Agent 生成章节草稿
  ↓
PM Agent 创建「QA 第 N 章」子任务 → QA Agent 校验
  ├─ 通过 → chapter-archive Skill 提交到 GitHub → PM 通知用户
  └─ 驳回 → PM 创建「修改第 N 章」子任务 → Writer 修改 → 重新 QA
  ↓
用户确认后，继续下一章
```

---

## QA 验证规则

QA Agent 基于提示词驱动，分两层校验：

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

在 Multica 工作区中向 PM Agent 发送新的 Issue，描述你想写的小说即可。PM Agent 会自动协调 Writer 和 QA Agent 完成创作。
