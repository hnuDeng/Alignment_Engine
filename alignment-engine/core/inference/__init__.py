"""
core.inference —— 显存管理与多模态推理调度服务

子模块：
- memory_manager: 显存状态机与紧急卸载
- model_loader:   4-bit 量化 + FP16 VLM 加载器
- batch_engine:   异步队列批处理引擎
"""
