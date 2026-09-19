"""
data_pipeline 包 —— 海量并发数据摄入总线。

子模块：
  - ray_dispatcher: 基于 Ray 的分布式 MediaDecoder Actor
  - kafka_streamer: Kafka 异步流消费者（幂等/DLQ/手动位移）
  - gpu_media_decoder: 绕过 PIL 的直接 GPU 解码管道
"""

from __future__ import annotations

__all__ = [
    "ray_dispatcher",
    "kafka_streamer",
    "gpu_media_decoder",
]
