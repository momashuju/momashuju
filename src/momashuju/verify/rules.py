"""确定性验证规则 — 零 LLM 成本的第一层质量过滤.

基于 README 中定义的 11 条确定性规则，定义数据结构与接口。
具体检测逻辑在后续开发中逐步实现。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    INFO = "info"         # 提示
    WARNING = "warning"   # 警告
    ERROR = "error"       # 错误（阻塞）


@dataclass
class RuleResult:
    """单条规则的检查结果."""

    rule_name: str
    passed: bool
    severity: Severity = Severity.INFO
    message: str = ""
    details: dict = field(default_factory=dict)
    # 匹配位置（行号或字符偏移）
    locations: list[int] = field(default_factory=list)


@dataclass
class Rule:
    """单条验证规则."""

    name: str
    description: str
    severity: Severity = Severity.WARNING

    def check(self, text: str) -> RuleResult:
        """执行规则检查。子类应覆盖此方法."""
        return RuleResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message=f"规则 '{self.name}' 未实现检查逻辑",
        )


class BannedPatternRule(Rule):
    """规则1: 禁止句式检测."""

    def __init__(
        self,
        patterns: list[str] | None = None,
        severity: Severity = Severity.WARNING,
    ):
        super().__init__(
            name="banned_patterns",
            description="检测禁止句式（如 '不是……而是……'）",
            severity=severity,
        )
        self._patterns = patterns or []

    def check(self, text: str) -> RuleResult:
        locations = []
        for pattern in self._patterns:
            for match in re.finditer(re.escape(pattern), text):
                locations.append(match.start())
        passed = len(locations) == 0
        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message="通过" if passed else f"发现 {len(locations)} 处禁止句式",
            details={"patterns": self._patterns, "count": len(locations)},
            locations=locations,
        )


class NoEmDashRule(Rule):
    """规则2: 破折号禁用."""

    def __init__(self, severity: Severity = Severity.WARNING):
        super().__init__(
            name="no_em_dash",
            description="检测破折号 '——' 使用",
            severity=severity,
        )

    def check(self, text: str) -> RuleResult:
        locations = [m.start() for m in re.finditer("——", text)]
        passed = len(locations) == 0
        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message="通过" if passed else f"发现 {len(locations)} 处破折号",
            details={"count": len(locations)},
            locations=locations,
        )


class TransitionDensityRule(Rule):
    """规则3: 过渡词密度控制."""

    def __init__(
        self,
        words: list[str] | None = None,
        max_per_1000_chars: float = 1.0,
        severity: Severity = Severity.WARNING,
    ):
        super().__init__(
            name="transition_density",
            description=f"过渡词密度 ≤ {max_per_1000_chars} 次/千字",
            severity=severity,
        )
        self._words = words or ["仿佛", "忽然", "竟然", "突然", "蓦然"]
        self._max_per_1000_chars = max_per_1000_chars

    def check(self, text: str) -> RuleResult:
        total_count = 0
        details: dict[str, int] = {}
        for word in self._words:
            count = text.count(word)
            if count > 0:
                details[word] = count
            total_count += count

        text_len = len(text)
        density = total_count / (text_len / 1000) if text_len > 0 else 0
        passed = density <= self._max_per_1000_chars

        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message=f"密度: {density:.2f}/千字 (阈值: {self._max_per_1000_chars})",
            details={"density": round(density, 2), "words": details, "total": total_count},
        )


class FatigueWordRule(Rule):
    """规则4: 高疲劳词频率控制."""

    def __init__(
        self,
        words: list[str] | None = None,
        max_per_chapter: int = 1,
        severity: Severity = Severity.WARNING,
    ):
        super().__init__(
            name="fatigue_words",
            description=f"疲劳词 ≤ {max_per_chapter} 次/章",
            severity=severity,
        )
        self._words = words or ["震撼", "惊骇", "恐惧", "颤抖", "战栗", "毛骨悚然"]
        self._max_per_chapter = max_per_chapter

    def check(self, text: str) -> RuleResult:
        details: dict[str, int] = {}
        exclusions: list[str] = []
        for word in self._words:
            count = text.count(word)
            if count > 0:
                details[word] = count
            if count > self._max_per_chapter:
                exclusions.append(word)

        passed = len(exclusions) == 0
        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message="通过" if passed else f"超标词: {exclusions}",
            details={"threshold": self._max_per_chapter, "counts": details, "exclusions": exclusions},
        )


class NoMetaNarrationRule(Rule):
    """规则5: 元叙事检测（编剧式旁白）."""

    def __init__(
        self,
        patterns: list[str] | None = None,
        severity: Severity = Severity.WARNING,
    ):
        super().__init__(
            name="no_meta_narration",
            description="检测元叙事/编剧式旁白",
            severity=severity,
        )
        self._patterns = patterns or ["读者朋友们", "各位看官", "值得一提的是", "我们来说说"]

    def check(self, text: str) -> RuleResult:
        found: list[str] = []
        for pattern in self._patterns:
            if pattern in text:
                found.append(pattern)
        passed = len(found) == 0
        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message="通过" if passed else f"发现元叙事: {found}",
            details={"found": found},
        )


class NoReportTermsRule(Rule):
    """规则6: 报告术语检测."""

    def __init__(
        self,
        terms: list[str] | None = None,
        severity: Severity = Severity.WARNING,
    ):
        super().__init__(
            name="no_report_terms",
            description="检测报告/论文式术语",
            severity=severity,
        )
        self._terms = terms or ["综上所述", "总而言之", "数据显示", "研究表明"]

    def check(self, text: str) -> RuleResult:
        found: list[str] = []
        for term in self._terms:
            if term in text:
                found.append(term)
        passed = len(found) == 0
        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message="通过" if passed else f"发现报告术语: {found}",
            details={"found": found},
        )


class NoAuthorPreachingRule(Rule):
    """规则7: 作者说教检测."""

    def __init__(
        self,
        words: list[str] | None = None,
        severity: Severity = Severity.WARNING,
    ):
        super().__init__(
            name="no_author_preaching",
            description="检测作者说教式词汇",
            severity=severity,
        )
        self._words = words or ["显然", "不言而喻", "众所周知", "毫无疑问"]

    def check(self, text: str) -> RuleResult:
        found: list[str] = []
        for word in self._words:
            if word in text:
                found.append(word)
        passed = len(found) == 0
        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message="通过" if passed else f"发现说教词汇: {found}",
            details={"found": found},
        )


class NoCollectiveReactionRule(Rule):
    """规则8: 集体反应检测."""

    def __init__(
        self,
        patterns: list[str] | None = None,
        severity: Severity = Severity.INFO,
    ):
        super().__init__(
            name="no_collective_reaction",
            description="检测集体反应（'全场震惊'类）",
            severity=severity,
        )
        self._patterns = patterns or ["全场震惊", "众人哗然", "所有人都", "大家纷纷", "满座皆惊"]

    def check(self, text: str) -> RuleResult:
        found: list[str] = []
        for pattern in self._patterns:
            if pattern in text:
                found.append(pattern)
        passed = len(found) == 0
        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message="通过" if passed else f"发现集体反应: {found}",
            details={"found": found},
        )


class ConsecutiveLeRule(Rule):
    """规则9: 连续"了"检测."""

    def __init__(
        self,
        max_consecutive: int = 4,
        severity: Severity = Severity.WARNING,
    ):
        super().__init__(
            name="consecutive_le",
            description=f"连续 '了' 结尾 ≤ {max_consecutive} 句",
            severity=severity,
        )
        self._max_consecutive = max_consecutive

    def check(self, text: str) -> RuleResult:
        # 按句号、感叹号、问号分句
        sentences = re.split(r"[。！？\n]", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        max_consec = 0
        current = 0
        locations: list[int] = []
        for i, sent in enumerate(sentences):
            if sent.endswith("了"):
                current += 1
                if current > self._max_consecutive:
                    locations.append(i)
            else:
                max_consec = max(max_consec, current)
                current = 0
        max_consec = max(max_consec, current)

        passed = max_consec < self._max_consecutive
        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message=f"最大连续: {max_consec} (阈值: {self._max_consecutive})",
            details={"max_consecutive": max_consec, "threshold": self._max_consecutive},
            locations=locations,
        )


class ParagraphLengthRule(Rule):
    """规则10: 段落长度控制."""

    def __init__(
        self,
        max_chars: int = 300,
        max_exceed_segments: int = 2,
        severity: Severity = Severity.INFO,
    ):
        super().__init__(
            name="paragraph_length",
            description=f"段落 ≤ {max_chars} 字，最多 {max_exceed_segments} 段超标",
            severity=severity,
        )
        self._max_chars = max_chars
        self._max_exceed_segments = max_exceed_segments

    def check(self, text: str) -> RuleResult:
        paragraphs = text.split("\n\n")
        exceed_count = 0
        exceed_lens: list[int] = []
        for i, para in enumerate(paragraphs):
            para_len = len(para.replace("\n", ""))
            if para_len > self._max_chars:
                exceed_count += 1
                exceed_lens.append(para_len)

        passed = exceed_count <= self._max_exceed_segments
        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message=f"超标段数: {exceed_count}/{len(paragraphs)} (阈值: {self._max_exceed_segments})",
            details={
                "total_paragraphs": len(paragraphs),
                "exceed_count": exceed_count,
                "max_chars": self._max_chars,
                "exceed_lengths": exceed_lens,
            },
        )


class CustomBannedRule(Rule):
    """规则11: 书籍专属禁止列表."""

    def __init__(
        self,
        words: list[str] | None = None,
        severity: Severity = Severity.WARNING,
    ):
        super().__init__(
            name="custom_banned",
            description="检测自定义禁止词汇",
            severity=severity,
        )
        self._words = words or []

    def check(self, text: str) -> RuleResult:
        if not self._words:
            return RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="无自定义禁止词，跳过",
            )

        found: dict[str, int] = {}
        for word in self._words:
            count = text.count(word)
            if count > 0:
                found[word] = count

        passed = len(found) == 0
        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message="通过" if passed else f"发现禁止词: {list(found.keys())}",
            details={"found": found},
        )


class RuleSet:
    """规则集 — 聚合多条规则，批量执行."""

    def __init__(self, rules: list[Rule] | None = None):
        self._rules = rules or []

    def add(self, rule: Rule) -> None:
        self._rules.append(rule)

    def check_all(self, text: str) -> list[RuleResult]:
        """执行所有规则，返回结果列表."""
        return [rule.check(text) for rule in self._rules]

    @property
    def passed(self, results: list[RuleResult] | None = None) -> bool:
        """是否有 ERROR 级别的失败."""
        if results is None:
            return True
        for r in results:
            if not r.passed and r.severity == Severity.ERROR:
                return False
        return True

    @classmethod
    def create_default(cls, config: dict | None = None) -> "RuleSet":
        """根据配置创建默认规则集（11 条规则）."""
        rules_config = config or {}
        rule_set = cls()

        # 规则1: 禁止句式
        bp_config = rules_config.get("banned_patterns", {})
        if bp_config.get("enabled", True):
            rule_set.add(BannedPatternRule(
                patterns=bp_config.get("patterns", []),
                severity=Severity.WARNING,
            ))

        # 规则2: 破折号
        if rules_config.get("no_em_dash", {}).get("enabled", True):
            rule_set.add(NoEmDashRule())

        # 规则3: 过渡词密度
        td_config = rules_config.get("transition_density", {})
        if td_config.get("enabled", True):
            rule_set.add(TransitionDensityRule(
                words=td_config.get("words"),
                max_per_1000_chars=td_config.get("max_per_1000_chars", 1),
            ))

        # 规则4: 疲劳词
        fw_config = rules_config.get("fatigue_words", {})
        if fw_config.get("enabled", True):
            rule_set.add(FatigueWordRule(
                words=fw_config.get("words"),
                max_per_chapter=fw_config.get("max_per_chapter", 1),
            ))

        # 规则5: 元叙事
        if rules_config.get("no_meta_narration", {}).get("enabled", True):
            rule_set.add(NoMetaNarrationRule())

        # 规则6: 报告术语
        if rules_config.get("no_report_terms", {}).get("enabled", True):
            rule_set.add(NoReportTermsRule())

        # 规则7: 作者说教
        if rules_config.get("no_author_preaching", {}).get("enabled", True):
            rule_set.add(NoAuthorPreachingRule())

        # 规则8: 集体反应
        if rules_config.get("no_collective_reaction", {}).get("enabled", True):
            rule_set.add(NoCollectiveReactionRule())

        # 规则9: 连续"了"
        cl_config = rules_config.get("consecutive_le", {})
        if cl_config.get("enabled", True):
            rule_set.add(ConsecutiveLeRule(
                max_consecutive=cl_config.get("max_consecutive", 4),
            ))

        # 规则10: 段落长度
        pl_config = rules_config.get("paragraph_length", {})
        if pl_config.get("enabled", True):
            rule_set.add(ParagraphLengthRule(
                max_chars=pl_config.get("max_chars", 300),
                max_exceed_segments=pl_config.get("max_exceed_segments", 2),
            ))

        # 规则11: 自定义禁止词
        cb_config = rules_config.get("custom_banned", {})
        if cb_config.get("enabled", True):
            rule_set.add(CustomBannedRule(
                words=cb_config.get("words", []),
            ))

        return rule_set
