import time
import subprocess
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any
from .sandbox_cgroup_manager import SandboxCgroupManager, ExecutionTimeoutException

class SandboxMode(Enum):
    DOCKER = "docker"
    SUBPROCESS = "subprocess"

@dataclass
class SandboxConfig:
    timeout_seconds: int = 10
    memory_limit: str = "512m"
    cpu_cores: float = 0.5
    max_output_bytes: int = 10000

@dataclass
class SandboxResult:
    success: bool
    exit_code: int
    execution_time_ms: float
    stdout: str
    timeout_reached: bool = False
    error: Optional[str] = None

class SandboxManager:
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        try:
            self.cgroup_manager = SandboxCgroupManager(memory_limit_mb=int(self.config.memory_limit.replace('m','')), cpu_quota=int(self.config.cpu_cores*100000))
            self.mode = SandboxMode.DOCKER if self.cgroup_manager.client else SandboxMode.SUBPROCESS
        except Exception:
            self.mode = SandboxMode.SUBPROCESS

    def get_info(self):
        return {
            "mode": self.mode.value,
            "timeout_seconds": self.config.timeout_seconds,
            "memory_limit": self.config.memory_limit
        }

    def execute(self, script_content: str) -> SandboxResult:
        start = time.time()
        try:
            if self.mode == SandboxMode.DOCKER:
                res = self.cgroup_manager.execute_script(script_content, timeout_seconds=self.config.timeout_seconds)
                exec_time = (time.time() - start) * 1000
                stdout = res["logs"][:self.config.max_output_bytes]
                return SandboxResult(success=res["success"], exit_code=res["code"], execution_time_ms=exec_time, stdout=stdout)
            else:
                # Fallback to subprocess
                try:
                    proc = subprocess.run(
                        ["python", "-c", script_content],
                        capture_output=True,
                        text=True,
                        timeout=self.config.timeout_seconds
                    )
                    exec_time = (time.time() - start) * 1000
                    stdout = proc.stdout[:self.config.max_output_bytes]
                    return SandboxResult(success=(proc.returncode == 0), exit_code=proc.returncode, execution_time_ms=exec_time, stdout=stdout)
                except subprocess.TimeoutExpired:
                    return SandboxResult(success=False, exit_code=-1, execution_time_ms=(time.time() - start) * 1000, stdout="", timeout_reached=True)
        except ExecutionTimeoutException:
            return SandboxResult(success=False, exit_code=-1, execution_time_ms=(time.time() - start) * 1000, stdout="", timeout_reached=True)
        except Exception as e:
            return SandboxResult(success=False, exit_code=-1, execution_time_ms=(time.time() - start) * 1000, stdout="", error=str(e))

    def execute_with_audit(self, script_content: str) -> SandboxResult:
        # Import dynamically to avoid circular import issues
        from .ast_taint_analyzer import audit_script
        report = audit_script(script_content)
        if not report.passed:
            return SandboxResult(success=False, exit_code=-1, execution_time_ms=0, stdout="", error="AST_AUDIT_FAILED")
        return self.execute(script_content)
