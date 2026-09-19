"""
测试 core.security 子系统 —— AST 污点分析器 + 沙盒执行器

覆盖范围：
- TaintAnalyzer 的污点源、传播、汇检测
- 各严重等级违规的触发条件
- SandboxManager 的超时、降级、审计集成
"""

from __future__ import annotations

import time

import pytest

from core.security.ast_taint_analyzer import (
    AuditReport,
    Severity,
    TaintAnalyzer,
    Violation,
    audit_script,
    is_safe,
)
from core.security.sandbox_manager import (
    SandboxConfig,
    SandboxManager,
    SandboxMode,
    SandboxResult,
)


# ══════════════════════════════════════════════════════════════
# AST Taint Analyzer 测试
# ══════════════════════════════════════════════════════════════

class TestTaintAnalyzerImports:
    """测试 Import 违规检测。"""

    def test_critical_module_os(self) -> None:
        """import os 应触发 CRITICAL。"""
        report = audit_script("import os\nos.system('ls')")
        assert report.passed is False
        assert report.critical_count >= 1

    def test_critical_module_subprocess(self) -> None:
        """import subprocess 应触发 CRITICAL。"""
        report = audit_script("import subprocess\nsubprocess.call(['ls'])")
        assert report.passed is False
        assert any(v.code_id == "IMPORT-001" for v in report.violations)

    def test_high_module_pickle(self) -> None:
        """import pickle 应触发 HIGH。"""
        report = audit_script("import pickle\ndata = pickle.loads(b'x')")
        assert report.passed is False
        assert any(v.severity == Severity.HIGH for v in report.violations)

    def test_from_import_os_system(self) -> None:
        """from os import system 应触发 CRITICAL。"""
        report = audit_script("from os import system\nsystem('ls')")
        assert report.passed is False
        assert any(v.code_id == "IMPORT-002" for v in report.violations)

    def test_safe_import_logging(self) -> None:
        """import logging 应安全通过。"""
        report = audit_script("import logging\nlogging.info('ok')")
        assert report.passed is True
        assert len(report.violations) == 0

    def test_safe_import_math(self) -> None:
        """import math 应安全通过。"""
        report = audit_script("import math\nx = math.sqrt(4)")
        assert report.passed is True


class TestTaintAnalyzerSinks:
    """测试 Sink 检测。"""

    def test_exec_call(self) -> None:
        """exec() 调用应触发 CRITICAL。"""
        report = audit_script("exec('print(1)')")
        assert report.passed is False
        assert any(v.code_id == "CALL-EXEC" for v in report.violations)

    def test_eval_call(self) -> None:
        """eval() 调用应触发 CRITICAL。"""
        report = audit_script("eval('1+1')")
        assert report.passed is False

    def test_dunder_import(self) -> None:
        """__import__() 调用应触发 CRITICAL。"""
        report = audit_script("__import__('os')")
        assert report.passed is False

    def test_compile_call(self) -> None:
        """compile() 调用应触发 CRITICAL。"""
        report = audit_script("compile('x=1', '<s>', 'exec')")
        assert report.passed is False


class TestTaintAnalyzerPropagation:
    """测试污点传播追踪。"""

    def test_taint_propagation_via_assignment(self) -> None:
        """污点变量赋值应传播到新变量。"""
        analyzer = TaintAnalyzer()
        report = analyzer.analyze(
            "import os\n"
            "x = os\n"
            "x.system('ls')"
        )
        assert report.passed is False
        assert len(report.tainted_variables) >= 1

    def test_taint_propagation_fstring(self) -> None:
        """f-string 中嵌入污点变量应被检测。"""
        analyzer = TaintAnalyzer()
        report = analyzer.analyze(
            "import os\n"
            "msg = f'path={os.getcwd()}'"
        )
        # f-string 中引用了污点变量 os
        assert len(report.violations) >= 1

    def test_taint_propagation_binop(self) -> None:
        """二元操作中使用污点变量应传播。"""
        analyzer = TaintAnalyzer()
        report = analyzer.analyze(
            "import os\n"
            "x = os.getcwd() + '/test'"
        )
        assert report.critical_count >= 1

    def test_function_args_are_tainted(self) -> None:
        """函数参数默认标记为污点源。"""
        analyzer = TaintAnalyzer()
        report = analyzer.analyze(
            "def process(data):\n"
            "    exec(data)\n"
        )
        assert report.passed is False
        assert any(v.code_id == "CALL-EXEC" for v in report.violations)

    def test_input_is_taint_source(self) -> None:
        """input() 返回值应标记为污点。"""
        analyzer = TaintAnalyzer()
        report = analyzer.analyze(
            "user_data = input('prompt: ')\n"
            "exec(user_data)"
        )
        assert report.passed is False
        assert "input()" in str(report.taint_sources)


class TestTaintAnalyzerAttributes:
    """测试敏感属性访问检测。"""

    def test_dunder_builtins(self) -> None:
        """访问 __builtins__ 应触发 HIGH。"""
        report = audit_script("x = __builtins__")
        assert any(v.code_id in ("ATTR-001", "NAME-001") for v in report.violations)

    def test_dunder_subclasses(self) -> None:
        """访问 __subclasses__ 应触发 HIGH。"""
        report = audit_script("x = object.__subclasses__()")
        assert any(v.code_id in ("ATTR-001", "NAME-001") for v in report.violations)


class TestTaintAnalyzerSafeScripts:
    """测试合法脚本应通过审查。"""

    def test_simple_data_processing(self) -> None:
        report = audit_script(
            "x = [1, 2, 3]\n"
            "y = [i * 2 for i in x]\n"
            "print(y)"
        )
        assert report.passed is True

    def test_logging_usage(self) -> None:
        report = audit_script(
            "import logging\n"
            "logger = logging.getLogger('test')\n"
            "logger.info('safe')"
        )
        assert report.passed is True

    def test_numpy_usage(self) -> None:
        report = audit_script(
            "import numpy as np\n"
            "arr = np.array([1, 2, 3])\n"
            "print(arr.mean())"
        )
        assert report.passed is True


class TestTaintAnalyzerEdgeCases:
    """测试边界情况。"""

    def test_syntax_error(self) -> None:
        """语法错误应被报告为 HIGH。"""
        report = audit_script("def foo(:")
        assert report.passed is False
        assert any(v.severity >= Severity.HIGH for v in report.violations)

    def test_empty_script(self) -> None:
        """空脚本应通过。"""
        report = audit_script("")
        assert report.passed is True

    def test_comment_only(self) -> None:
        """纯注释脚本应通过。"""
        report = audit_script("# safe comment\n# another")
        assert report.passed is True


# ══════════════════════════════════════════════════════════════
# SandboxManager 测试
# ══════════════════════════════════════════════════════════════

class TestSandboxManager:
    """测试沙盒执行器。"""

    def test_mode_detection(self) -> None:
        """应自动检测 Docker 可用性。"""
        sm = SandboxManager()
        assert sm.mode in (SandboxMode.DOCKER, SandboxMode.SUBPROCESS)

    def test_execute_safe_code(self) -> None:
        """安全代码应执行成功。"""
        sm = SandboxManager()
        result = sm.execute("print('hello sandbox')")
        assert result.success is True
        assert "hello sandbox" in result.stdout

    def test_execute_with_syntax_error(self) -> None:
        """语法错误代码应执行失败。"""
        sm = SandboxManager()
        result = sm.execute("def foo(:")
        assert result.success is False

    def test_timeout_mechanism(self) -> None:
        """超时应被正确捕获。"""
        config = SandboxConfig(timeout_seconds=2)
        sm = SandboxManager(config=config)
        result = sm.execute("import time; time.sleep(10)")
        assert result.success is False
        assert result.timeout_reached is True

    def test_execute_with_audit_passes(self) -> None:
        """通过审计的安全代码应执行成功。"""
        sm = SandboxManager()
        result = sm.execute_with_audit("print('audited and safe')")
        assert result.success is True

    def test_execute_with_audit_rejects_malicious(self) -> None:
        """未通过审计的代码应被拒绝执行。"""
        sm = SandboxManager()
        result = sm.execute_with_audit("import os\nos.system('ls')")
        assert result.success is False
        assert result.error == "AST_AUDIT_FAILED"

    def test_get_info(self) -> None:
        """get_info 应返回配置信息。"""
        sm = SandboxManager()
        info = sm.get_info()
        assert "mode" in info
        assert "timeout_seconds" in info
        assert "memory_limit" in info

    def test_custom_config(self) -> None:
        """支持自定义配置。"""
        config = SandboxConfig(
            timeout_seconds=10,
            memory_limit="512m",
            cpu_cores=2.0,
        )
        sm = SandboxManager(config=config)
        assert sm.config.timeout_seconds == 10
        assert sm.config.memory_limit == "512m"


class TestSandboxResult:
    """测试 SandboxResult 数据类。"""

    def test_result_fields(self) -> None:
        sm = SandboxManager()
        result = sm.execute("x = 1 + 1")
        assert isinstance(result.success, bool)
        assert isinstance(result.exit_code, int)
        assert isinstance(result.execution_time_ms, float)
        assert result.execution_time_ms > 0

    def test_output_truncation(self) -> None:
        """输出应按 max_output_bytes 截断。"""
        config = SandboxConfig(max_output_bytes=100)
        sm = SandboxManager(config=config)
        code = "print('x' * 1000)"
        result = sm.execute(code)
        assert len(result.stdout) <= 100 + 10  # 允许少量溢出


# ══════════════════════════════════════════════════════════════
# 集成测试：AST 审计 + 沙盒执行
# ══════════════════════════════════════════════════════════════

class TestSecurityIntegration:
    """测试完整安全流程。"""

    def test_full_pipeline_safe(self) -> None:
        """安全脚本：AST 通过 → 沙盒执行成功。"""
        sm = SandboxManager()
        code = (
            "import logging\n"
            "data = [1, 2, 3, 4, 5]\n"
            "result = sum(data) / len(data)\n"
            "logging.info('average: %s', result)\n"
            "print(result)"
        )
        result = sm.execute_with_audit(code)
        assert result.success is True
        assert "3.0" in result.stdout

    def test_full_pipeline_malicious(self) -> None:
        """恶意脚本：AST 拒绝 → 不执行。"""
        sm = SandboxManager()
        code = "import os\nos.system('rm -rf /')"
        result = sm.execute_with_audit(code)
        assert result.success is False
        assert result.error == "AST_AUDIT_FAILED"

    def test_full_pipeline_edge_case_import_then_exec(self) -> None:
        """间接攻击：先 import 再 exec。"""
        sm = SandboxManager()
        code = (
            "import os as dangerous_module\n"
            "exec('dangerous_module.system(\"ls\")')"
        )
        result = sm.execute_with_audit(code)
        assert result.success is False
