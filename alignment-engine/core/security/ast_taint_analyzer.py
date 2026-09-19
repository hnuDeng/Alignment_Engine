import ast
import builtins
from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Set, Any

class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class Violation:
    code_id: str
    severity: Severity
    description: str

@dataclass
class AuditReport:
    passed: bool
    violations: List[Violation] = field(default_factory=list)
    tainted_variables: Set[str] = field(default_factory=set)
    taint_sources: Set[str] = field(default_factory=set)
    
    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.CRITICAL)

class TaintAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.report = AuditReport(passed=True)
        self.tainted_vars: Set[str] = set()
        self.taint_srcs: Set[str] = set()
        self.critical_modules = {'os', 'subprocess', 'sys'}
        self.high_modules = {'pickle', 'socket'}
        
    def add_violation(self, code: str, sev: Severity, desc: str):
        self.report.violations.append(Violation(code, sev, desc))
        self.report.passed = False

    def analyze(self, source_code: str) -> AuditReport:
        try:
            tree = ast.parse(source_code)
            self.visit(tree)
        except SyntaxError as e:
            self.add_violation("SYNTAX", Severity.HIGH, f"Syntax error: {e}")
            
        self.report.tainted_variables = self.tainted_vars
        self.report.taint_sources = self.taint_srcs
        return self.report

    def visit_Import(self, node: ast.Import) -> Any:
        for name in node.names:
            if name.name in self.critical_modules:
                self.add_violation("IMPORT-001", Severity.CRITICAL, f"Blocked module {name.name}")
                self.taint_srcs.add(name.name)
                self.tainted_vars.add(name.name)
            elif name.name in self.high_modules:
                self.add_violation("IMPORT-003", Severity.HIGH, f"Blocked module {name.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.module in self.critical_modules:
            self.add_violation("IMPORT-002", Severity.CRITICAL, f"Blocked from import {node.module}")
            for name in node.names:
                self.taint_srcs.add(name.name)
                self.tainted_vars.add(name.name)
        self.generic_visit(node)

    def _is_node_tainted(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.tainted_vars
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == 'input':
                self.taint_srcs.add("input()")
                return True
        elif isinstance(node, ast.JoinedStr): # f-string
            for value in node.values:
                if isinstance(value, ast.FormattedValue):
                    if self._is_node_tainted(value.value):
                        return True
        elif isinstance(node, ast.BinOp):
            return self._is_node_tainted(node.left) or self._is_node_tainted(node.right)
        elif isinstance(node, ast.Attribute):
            return self._is_node_tainted(node.value)
        return False

    def visit_Assign(self, node: ast.Assign) -> Any:
        if self._is_node_tainted(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.tainted_vars.add(target.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            if self._is_node_tainted(node.func.value):
                # Tainted variable is being used as object for a method call (e.g. os.system)
                if func_name in ['system', 'call', 'Popen', 'run']:
                    self.add_violation("CALL-TAINTED", Severity.CRITICAL, "Tainted call")

        if func_name == 'exec':
            self.add_violation("CALL-EXEC", Severity.CRITICAL, "exec is forbidden")
        elif func_name == 'eval':
            self.add_violation("CALL-EVAL", Severity.CRITICAL, "eval is forbidden")
        elif func_name == '__import__':
            self.add_violation("CALL-IMPORT", Severity.CRITICAL, "__import__ is forbidden")
        elif func_name == 'compile':
            self.add_violation("CALL-COMPILE", Severity.CRITICAL, "compile is forbidden")
            
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if node.attr in ('__builtins__', '__subclasses__', '__globals__'):
            self.add_violation("ATTR-001", Severity.HIGH, f"Access to {node.attr}")
        self.generic_visit(node)
        
    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in ('__builtins__', '__subclasses__', '__globals__'):
            self.add_violation("NAME-001", Severity.HIGH, f"Access to {node.id}")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        # Function arguments are considered taint sources
        for arg in node.args.args:
            self.taint_srcs.add(arg.arg)
            self.tainted_vars.add(arg.arg)
        self.generic_visit(node)

def audit_script(source_code: str) -> AuditReport:
    analyzer = TaintAnalyzer()
    return analyzer.analyze(source_code)

def is_safe(source_code: str) -> bool:
    return audit_script(source_code).passed
