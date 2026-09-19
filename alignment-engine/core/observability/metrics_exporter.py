import time
import logging
import threading
from typing import Dict, Any, Optional
import pynvml

logger = logging.getLogger(__name__)

class MetricsException(Exception):
    """Base exception for hardware metrics operations."""
    pass

class NVMLInitializationException(MetricsException):
    """Raised when pynvml fails to initialize."""
    pass

class PrometheusExportException(MetricsException):
    """Raised when Prometheus formatting fails."""
    pass

class MetricsExporter:
    """
    Hardware probe utilizing pynvml.
    Resident thread monitors RTX 5060 VRAM at 10ms precision.
    Formats output as Prometheus Metrics.
    """
    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.latest_vram_used = 0
        self.latest_vram_total = 0
        
        try:
            pynvml.nvmlInit()
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(self.device_index)
            name = pynvml.nvmlDeviceGetName(self.handle)
            # if isinstance(name, bytes): name = name.decode()
            logger.info(f"Initialized NVML for device {self.device_index}: {name}")
        except pynvml.NVMLError as e:
            raise NVMLInitializationException(f"Failed to init NVML (No GPU?): {e}")
        except Exception as e:
            # Fallback for environments strictly without pynvml installed correctly
            logger.warning(f"NVML unavailable, entering mock mode: {e}")
            self.handle = None

    def start_probing(self):
        """Starts the 10ms precision resident thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._probe_loop, daemon=True)
        self.thread.start()
        logger.info("VRAM Probing thread started (10ms interval).")

    def stop_probing(self):
        """Stops the probing thread safely."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass

    def _probe_loop(self):
        """High-frequency polling loop."""
        while self.running:
            try:
                if self.handle:
                    info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
                    self.latest_vram_used = info.used
                    self.latest_vram_total = info.total
                else:
                    self.latest_vram_used = 4096 * 1024 * 1024 # mock 4GB
                    self.latest_vram_total = 8192 * 1024 * 1024 # mock 8GB RTX 5060
            except pynvml.NVMLError as e:
                logger.error(f"NVML Error in probe loop: {e}")
            except Exception as e:
                logger.error(f"Unexpected Error in probe loop: {e}")
                
            time.sleep(0.01) # 10ms precision

    def export_prometheus(self) -> str:
        """Formats the latest metrics in Prometheus text format."""
        try:
            used_mb = self.latest_vram_used / (1024 * 1024)
            total_mb = self.latest_vram_total / (1024 * 1024)
            
            lines = [
                "# HELP agent_vram_used_mb Current VRAM usage in MB",
                "# TYPE agent_vram_used_mb gauge",
                f"agent_vram_used_mb{{gpu=\"{self.device_index}\"}} {used_mb:.2f}",
                "# HELP agent_vram_total_mb Total VRAM in MB",
                "# TYPE agent_vram_total_mb gauge",
                f"agent_vram_total_mb{{gpu=\"{self.device_index}\"}} {total_mb:.2f}"
            ]
            return "\n".join(lines) + "\n"
        except Exception as e:
            raise PrometheusExportException(f"Failed to format metrics: {e}")
