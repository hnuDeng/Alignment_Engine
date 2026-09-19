try:
    import docker
except ImportError:
    docker = None
import logging
import time
from typing import Dict, Any, Optional
try:
    from docker.errors import DockerException, APIError, ContainerError
except ImportError:
    class DockerException(Exception): pass
    class APIError(Exception): pass
    class ContainerError(Exception): pass
import functools

logger = logging.getLogger(__name__)

class SandboxException(Exception):
    """Base exception for sandbox operations."""
    pass

class DockerConnectionException(SandboxException):
    """Raised when Docker daemon is unreachable."""
    pass

class CgroupAllocationException(SandboxException):
    """Raised when failing to allocate cgroups."""
    pass

class ExecutionTimeoutException(SandboxException):
    """Raised when sandbox execution exceeds time limit."""
    pass

def exponential_backoff_docker(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (DockerException, APIError) as e:
                    if i == max_retries - 1:
                        logger.error(f"Docker call {func.__name__} failed completely: {str(e)}")
                        raise DockerConnectionException(f"Docker failed: {str(e)}")
                    logger.warning(f"Docker call {func.__name__} failed, retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
        return wrapper
    return decorator

class SandboxCgroupManager:
    """
    Manages isolated execution of AI-generated code using Docker and Linux Cgroups.
    Enforces strict memory, CPU, and network egress limits.
    """
    def __init__(self, memory_limit_mb: int = 512, cpu_quota: int = 50000):
        try:
            self.client = docker.from_env()
        except DockerException as e:
            logger.warning(f"Could not connect to Docker. Will fallback if needed. {e}")
            self.client = None
            
        self.memory_limit = memory_limit_mb * 1024 * 1024 # Convert MB to Bytes
        self.cpu_quota = cpu_quota # 50000 out of 100000 = 0.5 CPU cores
        self.cpu_period = 100000

    @exponential_backoff_docker(max_retries=3)
    def execute_script(self, script_content: str, timeout_seconds: int = 10) -> Dict[str, Any]:
        """
        Executes a Python script in a heavily restricted Docker container.
        """
        if not self.client:
            raise DockerConnectionException("Docker daemon not available for Sandbox execution.")

        container = None
        try:
            # 1. Disable Network Egress
            # 2. Restrict Memory (512MB)
            # 3. Restrict CPU
            # 4. Drop all capabilities
            logger.info("Initializing secure Sandbox via Docker/Cgroups...")
            
            container = self.client.containers.run(
                image="python:3.11-slim",
                command=["python", "-c", script_content],
                detach=True,
                network_mode="none", # Strict No Egress
                mem_limit=self.memory_limit,
                memswap_limit=self.memory_limit, # Disable swap
                cpu_quota=self.cpu_quota,
                cpu_period=self.cpu_period,
                cap_drop=["ALL"], # Drop all Linux capabilities
                security_opt=["no-new-privileges:true"],
                read_only=True # Read-only root filesystem
            )

            # Wait for completion or timeout
            start_time = time.time()
            while container.status in ['created', 'running']:
                if time.time() - start_time > timeout_seconds:
                    container.kill()
                    raise ExecutionTimeoutException(f"Sandbox execution timed out after {timeout_seconds} seconds.")
                time.sleep(0.1)
                container.reload()

            result = container.wait()
            logs = container.logs().decode('utf-8')
            
            if result['StatusCode'] != 0:
                logger.error(f"Sandbox exited with code {result['StatusCode']}. Logs: {logs}")
                return {"success": False, "logs": logs, "code": result['StatusCode']}
                
            return {"success": True, "logs": logs, "code": 0}

        except ContainerError as e:
            logger.error(f"Container execution failed: {e}")
            return {"success": False, "logs": str(e), "code": -1}
        except Exception as e:
            if isinstance(e, ExecutionTimeoutException):
                raise
            raise CgroupAllocationException(f"Failed to configure or run Sandbox Cgroups: {e}")
        finally:
            if container:
                try:
                    container.remove(force=True)
                    logger.debug("Sandbox container aggressively removed.")
                except Exception as cleanup_error:
                    logger.error(f"Failed to remove sandbox container: {cleanup_error}")
