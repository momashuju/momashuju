"""测试 ScoreCalculator — 规则+审计 → 加权评分."""

import pytest
from momashuju.config import Config
from momashuju.verify.rules import RuleResult, Severity
from momashuju.verify.scoring import ScoreCalculator


@pytest.fixture
def config():
    return Config({
        "scoring": {
            "weights": {
                "plot_consistency": 0.20,
                "character_consistency": 0.20,
                "pacing": 0.15,
                "foreshadowing": 0.15,
                "readability": 0.10,
                "outline_adherence": 0.10,
                "style_compliance": 0.10,
            },
            "pass_threshold": 0.70,
        },
    })


@pytest.fixture
def all_pass_rules():
    return [
        RuleResult("r1", True, Severity.WARNING, "pass"),
        RuleResult("r2", True, Severity.WARNING, "pass"),
        RuleResult("r3", True, Severity.WARNING, "pass"),
    ]


@pytest.fixture
def some_fail_rules():
    return [
        RuleResult("r1", True, Severity.WARNING, "pass"),
        RuleResult("r2", False, Severity.WARNING, "fail"),
        RuleResult("r3", True, Severity.INFO, "pass"),
    ]


@pytest.fixture
def error_rules():
    return [
        RuleResult("r1", True, Severity.WARNING, "pass"),
        RuleResult("r2", False, Severity.ERROR, "fatal"),
    ]


@pytest.fixture
def perfect_llm_audit():
    return {
        "dimensions": {
            "plot_consistency": {"score": 10, "issues": [], "suggestions": []},
            "character_consistency": {"score": 10, "issues": [], "suggestions": []},
            "pacing": {"score": 10, "issues": [], "suggestions": []},
            "foreshadowing": {"score": 10, "issues": [], "suggestions": []},
            "readability": {"score": 10, "issues": [], "suggestions": []},
            "outline_adherence": {"score": 10, "issues": [], "suggestions": []},
        },
        "overall_comment": "完美。",
    }


@pytest.fixture
def mediocre_llm_audit():
    return {
        "dimensions": {
            "plot_consistency": {"score": 6, "issues": ["转折突兀"], "suggestions": []},
            "character_consistency": {"score": 5, "issues": ["角色OOC"], "suggestions": []},
            "pacing": {"score": 6, "issues": [], "suggestions": []},
            "foreshadowing": {"score": 5, "issues": ["伏笔未回收"], "suggestions": []},
            "readability": {"score": 7, "issues": [], "suggestions": []},
            "outline_adherence": {"score": 6, "issues": ["钩子缺失"], "suggestions": []},
        },
        "overall_comment": "质量一般。",
    }


class TestScoreCalculator:
    def test_perfect_score(self, config, all_pass_rules, perfect_llm_audit):
        calc = ScoreCalculator(config)
        result = calc.calculate(1, all_pass_rules, perfect_llm_audit)

        assert result.passed
        assert result.score == 1.0
        assert result.issues == []

    def test_rule_only_passes(self, config, all_pass_rules):
        """仅规则检查（无 LLM 审计）时应通过."""
        calc = ScoreCalculator(config)
        result = calc.calculate(1, all_pass_rules, None)

        # 仅 style_compliance 有分（0.10），其余维度默认满分
        # score = 1.0*0.10 + 1.0*0.90 = 1.0
        assert result.passed

    def test_rule_only_with_failures(self, config, some_fail_rules):
        """规则有 WARNING 级失败时仍可通过."""
        calc = ScoreCalculator(config)
        result = calc.calculate(1, some_fail_rules, None)

        # 规则: 2/3 = 0.667, style_compliance 权重 0.10
        # = 0.667*0.10 + 1.0*0.90 = 0.967
        assert result.passed
        assert len(result.issues) == 1  # 失败的那条规则

    def test_error_blocks(self, config, error_rules, perfect_llm_audit):
        """ERROR 级规则失败必须阻塞."""
        calc = ScoreCalculator(config)
        result = calc.calculate(1, error_rules, perfect_llm_audit)

        # 即使总分很高，ERROR 也阻塞
        assert not result.passed

    def test_mediocre_audit(self, config, all_pass_rules, mediocre_llm_audit):
        """中等质量审计 → 中等分数."""
        calc = ScoreCalculator(config)
        result = calc.calculate(1, all_pass_rules, mediocre_llm_audit)

        # 手动计算：
        # style: 1.0 * 0.10 = 0.10
        # plot: 0.6 * 0.20 = 0.12
        # char: 0.5 * 0.20 = 0.10
        # pacing: 0.6 * 0.15 = 0.09
        # fs: 0.5 * 0.15 = 0.075
        # readability: 0.7 * 0.10 = 0.07
        # outline: 0.6 * 0.10 = 0.06
        # total = 0.615
        assert result.score < 0.70
        assert not result.passed
        assert len(result.issues) > 0
        assert len(result.suggestions) > 0

    def test_weights_property(self, config):
        calc = ScoreCalculator(config)
        assert calc.weights["plot_consistency"] == 0.20
        assert calc.weights["style_compliance"] == 0.10
        assert calc.pass_threshold == 0.70

    def test_collects_issues_and_suggestions(self, config, some_fail_rules, mediocre_llm_audit):
        calc = ScoreCalculator(config)
        result = calc.calculate(1, some_fail_rules, mediocre_llm_audit)

        # 应该收集了规则问题 + LLM 审计问题
        assert len(result.issues) >= 5  # 1 rule fail + 4 llm issues
        assert len(result.suggestions) >= 1  # overall_comment is prepended
