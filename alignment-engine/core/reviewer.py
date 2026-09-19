"""审计与执行模块 (Reviewer) -- 负责脚本生成、AST 安全审计与安全执行。"""

from __future__ import annotations

import ast
import builtins
import logging
from typing import List, Optional, Set

from schemas import DriftReport, ReviewDecision

logger = logging.getLogger(__name__)

# AST 安全审计的黑名单配置
_BLOCKED_MODULES: Set[str] = {
    "os", "sys", "subprocess", "shutil", "socket", "http",
    "urllib", "requests", "ctypes", "importlib", "pathlib",
    "pickle", "shelve", "marshal", "code", "codeop",
    "compileall", "py_compile", "zipimport", "pkgutil",
}
_BLOCKED_FUNCTIONS: Set[str] = {
    "__import__", "exec", "eval", "compile", "globals", "locals",
    "getattr", "setattr", "delattr", "breakpoint", "exit", "quit",
    "open", "input", "help",
}
# 沙盒执行时从 builtins 中移除的函数。
# 不包含 __import__，因为正常的 import 语句依赖它；
# AST 检查器已在脚本执行前拦截了对危险模块的导入。
_BLOCKED_BUILTINS: Set[str] = {
    "exec", "eval", "compile", "breakpoint",
    "exit", "quit", "open", "input", "help",
}


class ASTSecurityChecker(ast.NodeVisitor):
    """AST 静态安全检查器。"""

    _SENSITIVE_NAMES: Set[str] = {
        "__builtins__", "__globals__", "__code__", "__import__",
    }

    def __init__(self) -> None:
        self.issues: List[str] = []

    def check(self, tree: ast.Module) -> List[str]:
        self.issues = []
        self.visit(tree)
        return self.issues

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            module_root = alias.name.split(".")[0]
            if module_root in _BLOCKED_MODULES:
                self.issues.append(
                    f"第 {node.lineno} 行: 禁止导入模块 '{alias.name}'"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is not None:
            module_root = node.module.split(".")[0]
            if module_root in _BLOCKED_MODULES:
                self.issues.append(
                    f"第 {node.lineno} 行: 禁止从模块 '{node.module}' 导入"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = self._extract_call_name(node.func)
        if func_name in _BLOCKED_FUNCTIONS:
            self.issues.append(
                f"第 {node.lineno} 行: 禁止调用 '{func_name}'"
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name):
            if node.value.id in _BLOCKED_MODULES:
                self.issues.append(
                    f"第 {node.lineno} 行: 禁止访问 '{node.value.id}.{node.attr}'"
                )
        if node.attr in ("__builtins__", "__globals__", "__code__"):
            self.issues.append(
                f"第 {node.lineno} 行: 禁止访问敏感属性 '{node.attr}'"
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """检查对 __builtins__ 等敏感名称的直接引用。"""
        if node.id in self._SENSITIVE_NAMES:
            self.issues.append(
                f"第 {node.lineno} 行: 禁止引用敏感名称 '{node.id}'"
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id in ("__builtins__", "__import__"):
                    self.issues.append(
                        f"第 {node.lineno} 行: 禁止覆盖 '{target.id}'"
                    )
        self.generic_visit(node)

    @staticmethod
    def _extract_call_name(func_node: ast.expr) -> Optional[str]:
        if isinstance(func_node, ast.Name):
            return func_node.id
        if isinstance(func_node, ast.Attribute):
            return func_node.attr
        return None


class Reviewer:
    """审计与执行模块。"""

    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self._checker = ASTSecurityChecker()
        logger.info("Reviewer 初始化完成 | dry_run=%s", dry_run)

    def generate_script(self, report: DriftReport) -> str:
        ids_repr = ", ".join(f'"{sid}"' for sid in report.drift_sample_ids)
        mode_comment = (
            "# [Mock 模式] 仅记录日志，不实际操作数据集"
            if self.dry_run
            else "# [Live 模式] 操作 FiftyOne 数据集"
        )

        script = f"""# FiftyOne 异常样本标记脚本 (自动生成)
# 分析模式: {report.analysis_mode}
# 漂移样本数: {len(report.drift_sample_ids)}
# 均值距离: {report.mean_distance}
# 阈值: {report.threshold}
{mode_comment}

import logging
_script_logger = logging.getLogger("reviewer.generated_script")

drift_ids = [{ids_repr}]

_script_logger.info("开始标记 %d 个漂移样本...", len(drift_ids))

marked_count = 0
for sample_id in drift_ids:
    try:
        sample = dataset[sample_id]
        current_tags = list(sample.tags) if sample.tags else []
        if "needs_review" not in current_tags:
            current_tags.append("needs_review")
            sample.tags = current_tags
            sample.save()
            marked_count += 1
            _script_logger.info("已标记样本 %s", sample_id)
        else:
            _script_logger.info("样本 %s 已标记，跳过", sample_id)
    except Exception as e:
        _script_logger.warning("标记样本 %s 失败: %s", sample_id, e)

_script_logger.info("标记完成: %d/%d 个样本已标记", marked_count, len(drift_ids))
"""
        logger.info("已生成 FiftyOne 更新脚本 (%d 字符)", len(script))
        return script

    def ast_static_check(self, script: str) -> ReviewDecision:
        issues: List[str] = []
        try:
            tree = ast.parse(script, mode="exec")
        except SyntaxError as exc:
            issues.append(f"语法错误: {exc}")
            logger.error("AST 解析失败: %s", exc)
            return ReviewDecision(
                generated_script=script,
                ast_check_passed=False,
                ast_issues=issues,
                executed=False,
                execution_log=f"AST 解析失败: {exc}",
            )
        issues = self._checker.check(tree)
        passed = len(issues) == 0
        if passed:
            logger.info("AST 安全检查通过")
        else:
            logger.warning(
                "AST 安全检查发现 %d 个问题: %s",
                len(issues), "; ".join(issues),
            )
        return ReviewDecision(
            generated_script=script,
            ast_check_passed=passed,
            ast_issues=issues,
            executed=False,
            execution_log=None,
        )

    def execute(self, script: str) -> ReviewDecision:
        decision = self.ast_static_check(script)
        if not decision.ast_check_passed:
            logger.error("脚本未通过 AST 安全检查，拒绝执行")
            return ReviewDecision(
                generated_script=script,
                ast_check_passed=False,
                ast_issues=decision.ast_issues,
                executed=False,
                execution_log="脚本未通过 AST 安全检查，拒绝执行",
            )
        if self.dry_run:
            log_msg = (
                "[Dry-Run] 脚本已通过 AST 安全检查。"
                "Mock 模式下不实际执行，仅记录日志。\n"
                f"脚本长度: {len(script)} 字符\n"
                f"AST 问题数: 0"
            )
            logger.info(log_msg)
            return ReviewDecision(
                generated_script=script,
                ast_check_passed=True,
                ast_issues=[],
                executed=True,
                execution_log=log_msg,
            )
        try:
            safe_builtins = {}
            for name in dir(builtins):
                if name not in _BLOCKED_BUILTINS:
                    safe_builtins[name] = getattr(builtins, name)
            sandbox_globals = {"__builtins__": safe_builtins}
            sandbox_locals = {}
            exec(
                compile(script, "<reviewer_script>", "exec"),
                sandbox_globals,
                sandbox_locals,
            )
            log_msg = "脚本执行成功"
            logger.info(log_msg)
        except Exception as exc:
            log_msg = f"脚本执行失败: {type(exc).__name__}: {exc}"
            logger.error(log_msg)
        return ReviewDecision(
            generated_script=script,
            ast_check_passed=True,
            ast_issues=[],
            executed=True,
            execution_log=log_msg,
        )
