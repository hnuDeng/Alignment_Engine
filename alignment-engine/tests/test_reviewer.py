"""
单元测试 —— 审计与执行模块 (core/reviewer.py)

覆盖范围：
- 脚本生成的正确性
- AST 安全检查的拦截能力（危险模块、危险函数、敏感属性）
- 合法脚本的放行
- Dry-Run 模式执行
- Live 模式沙盒执行
"""

from __future__ import annotations

import pytest

from schemas import DriftReport, DriftSample, ReviewDecision
from core.reviewer import Reviewer, ASTSecurityChecker


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------
def _make_drift_report(
    sample_ids: list[str] | None = None,
) -> DriftReport:
    """创建一个测试用的 DriftReport。"""
    if sample_ids is None:
        sample_ids = ["id-aaa-001", "id-bbb-002", "id-ccc-003"]
    samples = [
        DriftSample(
            image_id=sid,
            drift_score=3.5 + i * 0.5,
            reason=f"样本 {sid} 距离过大",
        )
        for i, sid in enumerate(sample_ids)
    ]
    return DriftReport(
        drift_samples=samples,
        drift_sample_ids=sample_ids,
        mean_distance=2.0,
        threshold=3.0,
        analysis_mode="mock_numpy",
    )


# ---------------------------------------------------------------------------
# AST 安全检查器测试
# ---------------------------------------------------------------------------
class TestASTSecurityChecker:
    """测试 ASTSecurityChecker 的各种危险模式检测。"""

    def setup_method(self) -> None:
        self.checker = ASTSecurityChecker()

    # --- 危险 import 检测 ---
    @pytest.mark.parametrize(
        "script,module",
        [
            ("import os", "os"),
            ("import sys", "sys"),
            ("import subprocess", "subprocess"),
            ("import shutil", "shutil"),
            ("import socket", "socket"),
            ("import http.client", "http"),
            ("import urllib.request", "urllib"),
            ("import ctypes", "ctypes"),
            ("import importlib", "importlib"),
            ("import pickle", "pickle"),
        ],
    )
    def test_block_dangerous_imports(self, script: str, module: str) -> None:
        """应拦截对危险模块的 import。"""
        import ast
        tree = ast.parse(script)
        issues = self.checker.check(tree)
        assert len(issues) >= 1
        assert module in issues[0]

    @pytest.mark.parametrize(
        "script,module",
        [
            ("from os import system", "os"),
            ("from sys import exit", "sys"),
            ("from subprocess import call", "subprocess"),
            ("from os.path import join", "os"),
        ],
    )
    def test_block_from_imports(self, script: str, module: str) -> None:
        """应拦截 from ... import 形式的危险导入。"""
        import ast
        tree = ast.parse(script)
        issues = self.checker.check(tree)
        assert len(issues) >= 1
        assert module in issues[0]

    # --- 危险函数调用检测 ---
    @pytest.mark.parametrize(
        "script,func",
        [
            ("exec('print(1)')", "exec"),
            ("eval('1+1')", "eval"),
            ("__import__('os')", "__import__"),
            ("compile('x=1', '<s>', 'exec')", "compile"),
            ("globals()", "globals"),
            ("locals()", "locals"),
            ("getattr(obj, 'x')", "getattr"),
            ("setattr(obj, 'x', 1)", "setattr"),
            ("delattr(obj, 'x')", "delattr"),
            ("breakpoint()", "breakpoint"),
        ],
    )
    def test_block_dangerous_calls(self, script: str, func: str) -> None:
        """应拦截危险的内置函数调用。"""
        import ast
        tree = ast.parse(script)
        issues = self.checker.check(tree)
        assert len(issues) >= 1
        assert func in issues[0]

    # --- 敏感属性访问检测 ---
    def test_block_os_system_access(self) -> None:
        """应拦截 os.system 等属性访问。"""
        import ast
        tree = ast.parse("os.system('ls')")
        issues = self.checker.check(tree)
        assert any("os.system" in i for i in issues)

    def test_block_builtins_access(self) -> None:
        """应拦截 __builtins__ 访问。"""
        import ast
        tree = ast.parse("x = __builtins__")
        issues = self.checker.check(tree)
        assert any("__builtins__" in i for i in issues)

    def test_block_builtins_assignment(self) -> None:
        """应拦截对 __builtins__ 的赋值。"""
        import ast
        tree = ast.parse("__builtins__ = {}")
        issues = self.checker.check(tree)
        assert any("__builtins__" in i for i in issues)

    # --- 语法错误检测 ---
    def test_syntax_error_reported(self) -> None:
        """语法错误应被捕获并报告。"""
        decision = Reviewer(dry_run=True).ast_static_check(
            "def foo(:"  # 语法错误
        )
        assert decision.ast_check_passed is False
        assert any("语法错误" in i for i in decision.ast_issues)

    # --- 合法脚本放行 ---
    def test_allow_safe_script(self) -> None:
        """合法的 FiftyOne 脚本应通过检查。"""
        import ast
        safe_script = '''
import logging
logger = logging.getLogger("test")
drift_ids = ["id-1", "id-2"]
marked = 0
for sid in drift_ids:
    logger.info("标记 %s", sid)
    marked += 1
logger.info("完成: %d", marked)
'''
        tree = ast.parse(safe_script)
        issues = self.checker.check(tree)
        assert len(issues) == 0

    def test_allow_logging_import(self) -> None:
        """logging 模块应被允许导入。"""
        import ast
        tree = ast.parse("import logging")
        issues = self.checker.check(tree)
        assert len(issues) == 0

    def test_allow_math_import(self) -> None:
        """math 模块应被允许导入。"""
        import ast
        tree = ast.parse("import math\nx = math.sqrt(4)")
        issues = self.checker.check(tree)
        assert len(issues) == 0

    # --- 复合攻击检测 ---
    def test_block_disguised_attack(self) -> None:
        """应检测到伪装在变量赋值后的危险调用。"""
        import ast
        script = '''
import os
x = 1
y = 2
os.system("rm -rf /")
'''
        tree = ast.parse(script)
        issues = self.checker.check(tree)
        assert len(issues) >= 2  # import os + os.system


# ---------------------------------------------------------------------------
# Reviewer 测试
# ---------------------------------------------------------------------------
class TestReviewer:
    """测试 Reviewer 的脚本生成、审计和执行功能。"""

    def setup_method(self) -> None:
        self.reviewer = Reviewer(dry_run=True)

    # --- 脚本生成 ---
    def test_generate_script_contains_ids(self) -> None:
        """生成的脚本应包含所有漂移样本 ID。"""
        report = _make_drift_report()
        script = self.reviewer.generate_script(report)
        for sid in report.drift_sample_ids:
            assert sid in script

    def test_generate_script_contains_needs_review(self) -> None:
        """生成的脚本应包含 'needs_review' 标签操作。"""
        report = _make_drift_report()
        script = self.reviewer.generate_script(report)
        assert "needs_review" in script

    def test_generate_script_is_valid_python(self) -> None:
        """生成的脚本应是合法的 Python 代码。"""
        import ast
        report = _make_drift_report()
        script = self.reviewer.generate_script(report)
        # 不应抛出 SyntaxError
        tree = ast.parse(script)
        assert tree is not None

    def test_generate_script_contains_metadata(self) -> None:
        """生成的脚本应包含分析模式等元数据注释。"""
        report = _make_drift_report()
        script = self.reviewer.generate_script(report)
        assert "mock_numpy" in script
        assert "2.0" in script  # mean_distance
        assert "3.0" in script  # threshold

    def test_generate_script_dry_run_comment(self) -> None:
        """Dry-Run 模式应包含 Mock 模式注释。"""
        report = _make_drift_report()
        script = self.reviewer.generate_script(report)
        assert "Mock 模式" in script

    def test_generate_script_live_comment(self) -> None:
        """Live 模式应包含 Live 模式注释。"""
        reviewer = Reviewer(dry_run=False)
        report = _make_drift_report()
        script = reviewer.generate_script(report)
        assert "Live 模式" in script

    # --- AST 审计 ---
    def test_ast_check_passes_for_generated_script(self) -> None:
        """生成的脚本应通过 AST 安全检查。"""
        report = _make_drift_report()
        script = self.reviewer.generate_script(report)
        decision = self.reviewer.ast_static_check(script)
        assert decision.ast_check_passed is True
        assert len(decision.ast_issues) == 0

    def test_ast_check_fails_for_malicious_script(self) -> None:
        """恶意脚本应被 AST 检查拦截。"""
        malicious = "import os\nos.system('rm -rf /')"
        decision = self.reviewer.ast_static_check(malicious)
        assert decision.ast_check_passed is False
        assert len(decision.ast_issues) >= 1

    def test_ast_check_fails_for_exec(self) -> None:
        """包含 exec() 的脚本应被拦截。"""
        decision = self.reviewer.ast_static_check("exec('print(1)')")
        assert decision.ast_check_passed is False

    def test_ast_check_fails_for_eval(self) -> None:
        """包含 eval() 的脚本应被拦截。"""
        decision = self.reviewer.ast_static_check("eval('1+1')")
        assert decision.ast_check_passed is False

    def test_ast_check_fails_for_dunder_import(self) -> None:
        """包含 __import__() 的脚本应被拦截。"""
        decision = self.reviewer.ast_static_check("__import__('os')")
        assert decision.ast_check_passed is False

    def test_ast_check_fails_for_syntax_error(self) -> None:
        """语法错误的脚本应被拦截。"""
        decision = self.reviewer.ast_static_check("def foo(:")
        assert decision.ast_check_passed is False

    # --- Dry-Run 执行 ---
    def test_dry_run_execute_succeeds(self) -> None:
        """Dry-Run 模式下，合法脚本应标记为已执行。"""
        report = _make_drift_report()
        script = self.reviewer.generate_script(report)
        decision = self.reviewer.execute(script)
        assert decision.ast_check_passed is True
        assert decision.executed is True
        assert "Dry-Run" in (decision.execution_log or "")

    def test_dry_run_execute_refuses_malicious(self) -> None:
        """Dry-Run 模式下，恶意脚本仍应被拒绝。"""
        malicious = "import os\nos.system('ls')"
        decision = self.reviewer.execute(malicious)
        assert decision.ast_check_passed is False
        assert decision.executed is False

    # --- Live 执行 ---
    def test_live_execute_safe_script(self) -> None:
        """Live 模式下，安全脚本应在沙盒中执行成功。"""
        reviewer = Reviewer(dry_run=False)
        safe_script = '''
import logging
logger = logging.getLogger("test_live")
logger.info("安全脚本执行成功")
result = 1 + 1
'''
        decision = reviewer.execute(safe_script)
        assert decision.ast_check_passed is True
        assert decision.executed is True
        assert "成功" in (decision.execution_log or "")

    def test_live_execute_blocks_os(self) -> None:
        """Live 模式下，包含 os 的脚本应被 AST 拦截。"""
        reviewer = Reviewer(dry_run=False)
        malicious = "import os\nos.system('echo hacked')"
        decision = reviewer.execute(malicious)
        assert decision.executed is False


# ---------------------------------------------------------------------------
# ReviewDecision 完整性测试
# ---------------------------------------------------------------------------
class TestReviewDecisionCompleteness:
    """测试 ReviewDecision 各字段的正确性。"""

    def test_full_pipeline_decision_fields(self) -> None:
        """完整流水线应产生所有字段均非 None 的决策（execution_log 除外）。"""
        reviewer = Reviewer(dry_run=True)
        report = _make_drift_report()
        script = reviewer.generate_script(report)
        decision = reviewer.execute(script)

        assert isinstance(decision, ReviewDecision)
        assert len(decision.generated_script) > 0
        assert decision.ast_check_passed is True
        assert decision.ast_issues == []
        assert decision.executed is True
        assert decision.execution_log is not None
