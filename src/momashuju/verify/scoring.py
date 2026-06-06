"""ScoreCalculator — 规则检查 + LLM 审计 → 加权评分.

将两层验证结果合并为单一的 ChapterAuditResult，
包含加权总分、各维度明细和通过/失败判定。
"""

from __future__ import annotations

from typing import Any

from momashuju.config import Config
from momashuju.spec.models import ChapterAuditResult
from momashuju.verify.rules import RuleResult, Severity


class ScoreCalculator:
    """评分计算器.

    合并两层验证结果：
    - Layer 1: 确定性规则（style_compliance）
    - Layer 2: LLM 审计（其余 6 个维度）

    权重从 config (defaults.yaml) 读取。
    """

    # 规则检查对应的评分维度
    RULE_DIMENSION = "style_compliance"

    # 默认权重（与 defaults.yaml 保持同步）
    DEFAULT_WEIGHTS = {
        "plot_consistency": 0.20,
        "character_consistency": 0.20,
        "pacing": 0.15,
        "foreshadowing": 0.15,
        "readability": 0.10,
        "outline_adherence": 0.10,
        "style_compliance": 0.10,
    }

    def __init__(self, config: Config) -> None:
        scoring = config.get("scoring", {})
        self._weights = scoring.get("weights", None) or self.DEFAULT_WEIGHTS
        self._pass_threshold = scoring.get("pass_threshold", 0.70)

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    @property
    def pass_threshold(self) -> float:
        return self._pass_threshold

    def calculate(
        self,
        chapter_number: int,
        rule_results: list[RuleResult],
        llm_audit: dict[str, Any] | None = None,
    ) -> ChapterAuditResult:
        """计算综合评分.

        Args:
            chapter_number: 章节序号
            rule_results: 确定性规则检查结果列表
            llm_audit: LLM 审计结果（dict），如果为 None 则仅使用规则评分

        Returns:
            ChapterAuditResult（含总分、各维度明细、问题列表）
        """
        # 1. 计算规则分（style_compliance）
        total_rules = len(rule_results)
        passed_rules = sum(1 for r in rule_results if r.passed)
        rule_score = passed_rules / total_rules if total_rules > 0 else 1.0

        # 2. 初始化维度分数
        dimension_scores: dict[str, float] = {
            self.RULE_DIMENSION: rule_score,
        }
        all_issues: list[str] = []
        all_suggestions: list[str] = []

        # 3. 收集规则层问题
        for r in rule_results:
            if not r.passed:
                issue = f"[规则:{r.rule_name}] {r.message}"
                all_issues.append(issue)

        # 4. 合并 LLM 审计结果
        llm_audit_data: dict[str, Any] = {}
        if llm_audit:
            dimensions = llm_audit.get("dimensions", {})
            for dim_name, dim_data in dimensions.items():
                raw_score = dim_data.get("score", 10)
                # 转换为 0-1 范围
                dimension_scores[dim_name] = raw_score / 10.0

                # 收集问题和建议
                for issue in dim_data.get("issues", []):
                    all_issues.append(f"[{dim_name}] {issue}")
                for suggestion in dim_data.get("suggestions", []):
                    all_suggestions.append(f"[{dim_name}] {suggestion}")

            llm_audit_data = llm_audit
            if llm_audit.get("overall_comment"):
                all_suggestions.insert(0, f"综合评价: {llm_audit['overall_comment']}")

        # 5. 计算加权总分
        total_score = 0.0
        total_weight = 0.0
        for dim_name, weight in self._weights.items():
            if dim_name in dimension_scores:
                score = dimension_scores[dim_name]
            else:
                # LLM 审计未覆盖的维度默认满分（不扣分）
                score = 1.0
            total_score += score * weight
            total_weight += weight

        # 如果某些维度没有分数（如 LLM 审计未覆盖），按比例调整
        if total_weight > 0 and total_weight < 1.0:
            # 缺失维度的分数按满分计
            total_score += (1.0 - total_weight)
            total_weight = 1.0

        # 6. 判定是否通过
        has_errors = any(
            not r.passed and r.severity == Severity.ERROR
            for r in rule_results
        )
        passed = (not has_errors) and (total_score >= self._pass_threshold)

        # 7. 序列化规则结果
        rule_results_data = [
            {
                "rule_name": r.rule_name,
                "passed": r.passed,
                "severity": r.severity.value,
                "message": r.message,
            }
            for r in rule_results
        ]

        return ChapterAuditResult(
            chapter_number=chapter_number,
            passed=passed,
            score=round(total_score, 4),
            rule_results=rule_results_data,
            llm_audit=llm_audit_data,
            issues=all_issues,
            suggestions=all_suggestions,
        )
