"""
core.observability 包 —— APM 与分布式追踪引擎。

子模块：
  - agent_telemetry: OpenTelemetry Span 注入
  - metrics_exporter: pynvml GPU 探针 + Prometheus 格式输出
"""

from __future__ import annotations

__all__ = [
    "agent_telemetry",
    "metrics_exporter",
]
