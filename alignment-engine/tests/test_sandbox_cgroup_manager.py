import pytest
from unittest.mock import MagicMock, patch
from core.security.sandbox_cgroup_manager import (
    SandboxCgroupManager,
    exponential_backoff_docker,
    DockerConnectionException,
    CgroupAllocationException,
    ExecutionTimeoutException,
    DockerException,
    APIError
)

class TestSandboxCgroupManager:
    @patch('core.security.sandbox_cgroup_manager.docker')
    def test_initialization_success(self, mock_docker):
        mock_docker.from_env.return_value = MagicMock()
        manager = SandboxCgroupManager(memory_limit_mb=128, cpu_quota=20000)
        assert manager.client is not None
        assert manager.memory_limit == 128 * 1024 * 1024
        assert manager.cpu_quota == 20000
        assert manager.cpu_period == 100000

    @patch('core.security.sandbox_cgroup_manager.docker')
    def test_initialization_docker_exception(self, mock_docker):
        mock_docker.errors.DockerException = DockerException
        mock_docker.from_env.side_effect = DockerException("Failed to connect")
        manager = SandboxCgroupManager()
        assert manager.client is None

    @patch('core.security.sandbox_cgroup_manager.docker')
    def test_execute_script_no_client(self, mock_docker):
        manager = SandboxCgroupManager()
        manager.client = None
        with pytest.raises(DockerConnectionException):
            manager.execute_script("print(1)")

    @patch('time.sleep', return_value=None)
    def test_exponential_backoff_decorator(self, mock_sleep):
        mock_func = MagicMock()
        mock_func.side_effect = [DockerException("err1"), DockerException("err2"), "success"]

        @exponential_backoff_docker(max_retries=3, base_delay=0.1)
        def dummy_call():
            return mock_func()
        
        res = dummy_call()
        assert res == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2

    @patch('time.sleep', return_value=None)
    def test_exponential_backoff_decorator_failure(self, mock_sleep):
        mock_func = MagicMock()
        mock_func.side_effect = APIError("err1")

        @exponential_backoff_docker(max_retries=2, base_delay=0.1)
        def dummy_call():
            return mock_func()
        
        with pytest.raises(DockerConnectionException):
            dummy_call()

    @patch('core.security.sandbox_cgroup_manager.docker')
    def test_execute_script_success(self, mock_docker):
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.status = 'exited'
        mock_container.wait.return_value = {'StatusCode': 0}
        mock_container.logs.return_value = b"Hello\n"
        mock_client.containers.run.return_value = mock_container
        
        manager = SandboxCgroupManager()
        manager.client = mock_client
        
        result = manager.execute_script("print('Hello')")
        assert result['success'] is True
        assert result['code'] == 0
        assert result['logs'] == "Hello\n"
        mock_container.remove.assert_called_once_with(force=True)

    @patch('core.security.sandbox_cgroup_manager.docker')
    @patch('time.time')
    def test_execute_script_timeout(self, mock_time, mock_docker):
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.status = 'running'
        mock_client.containers.run.return_value = mock_container
        
        # Simulate time passing to trigger timeout
        mock_time.side_effect = [100.0, 100.1, 101.5, 115.0]
        
        manager = SandboxCgroupManager()
        manager.client = mock_client
        
        with pytest.raises(ExecutionTimeoutException):
            manager.execute_script("while True: pass", timeout_seconds=10)
            
        mock_container.kill.assert_called_once()
        mock_container.remove.assert_called_once_with(force=True)

    @patch('core.security.sandbox_cgroup_manager.docker')
    def test_execute_script_non_zero_exit(self, mock_docker):
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.status = 'exited'
        mock_container.wait.return_value = {'StatusCode': 1}
        mock_container.logs.return_value = b"Error"
        mock_client.containers.run.return_value = mock_container
        
        manager = SandboxCgroupManager()
        manager.client = mock_client
        
        result = manager.execute_script("import sys; sys.exit(1)")
        assert result['success'] is False
        assert result['code'] == 1
        assert result['logs'] == "Error"

    @patch('core.security.sandbox_cgroup_manager.docker')
    def test_execute_script_general_exception(self, mock_docker):
        mock_client = MagicMock()
        mock_client.containers.run.side_effect = Exception("Unexpected error")
        
        manager = SandboxCgroupManager()
        manager.client = mock_client
        
        with pytest.raises(CgroupAllocationException):
            manager.execute_script("print(1)")
