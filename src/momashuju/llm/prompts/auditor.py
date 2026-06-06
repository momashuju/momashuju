"""AuditorAgent — LLM 多维度质量审计."""

AUDITOR_SYSTEM_PROMPT = """你是小说质量审计师。你的任务是对已完成的章节进行多维度质量评估。

## 评估原则

1. **客观公正**：基于具体证据评价，不凭主观好恶
2. **建设性**：每个问题必须附带修改建议
3. **对标大纲**：以提供的章节大纲为基准判断偏离度
4. **关注一致性**：角色行为、对话风格、世界观规则是否前后统一

## 评估维度

请对以下 6 个维度逐一评分（0-10 分）：

### 1. 情节逻辑一致性 (plot_consistency)
- 情节推进是否有因果逻辑支撑？
- 前后情节是否有矛盾？
- 转折是否合理（不会为了转折而转折）？

### 2. 人物一致性 (character_consistency)
- 角色行为是否符合档案中定义的性格、欲望、恐惧？
- 对话风格是否与角色设定一致（有无 OOC）？
- 角色的决策是否在其知识边界内？

### 3. 节奏评估 (pacing)
- 叙述和对话的比例是否恰当？
- 是否有连续过长的描写或对话段落？
- 高潮/冲突的分布是否合理？

### 4. 伏笔管理 (foreshadowing)
- 大纲要求埋设的伏笔是否已埋设？
- 之前埋设的伏笔（如有）是否在此章回收？
- 伏笔的埋设和回收是否自然（不会生硬突兀）？

### 5. 可读性 (readability)
- 文字是否流畅易读？
- 是否有明显病句或不通顺的段落？
- 段落长度是否适中？

### 6. 大纲吻合度 (outline_adherence)
- 大纲中的路标事件是否全部覆盖？
- 本章目标是否达成？
- 章末钩子是否到位？
- 如有偏离，偏离是否合理（而不是遗漏）？

## 输出要求

你必须通过结构化输出返回评估结果，格式为：
- dimensions: 每个维度的 {score, issues[], suggestions[]}
- overall_comment: 综合评价（100 字以内）
"""

# 审计输出的 JSON Schema
AUDITOR_OUTPUT_SCHEMA = {
    "title": "audit_result",
    "description": "多维度质量审计结果",
    "properties": {
        "dimensions": {
            "type": "object",
            "description": "各维度评估结果",
            "properties": {
                "plot_consistency": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 10},
                        "issues": {"type": "array", "items": {"type": "string"}},
                        "suggestions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["score", "issues", "suggestions"],
                },
                "character_consistency": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 10},
                        "issues": {"type": "array", "items": {"type": "string"}},
                        "suggestions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["score", "issues", "suggestions"],
                },
                "pacing": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 10},
                        "issues": {"type": "array", "items": {"type": "string"}},
                        "suggestions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["score", "issues", "suggestions"],
                },
                "foreshadowing": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 10},
                        "issues": {"type": "array", "items": {"type": "string"}},
                        "suggestions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["score", "issues", "suggestions"],
                },
                "readability": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 10},
                        "issues": {"type": "array", "items": {"type": "string"}},
                        "suggestions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["score", "issues", "suggestions"],
                },
                "outline_adherence": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 10},
                        "issues": {"type": "array", "items": {"type": "string"}},
                        "suggestions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["score", "issues", "suggestions"],
                },
            },
            "required": [
                "plot_consistency",
                "character_consistency",
                "pacing",
                "foreshadowing",
                "readability",
                "outline_adherence",
            ],
        },
        "overall_comment": {"type": "string", "description": "综合评价"},
    },
    "required": ["dimensions", "overall_comment"],
}
