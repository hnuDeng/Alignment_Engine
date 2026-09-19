"""
多智能体可视分析引擎 (Data-Centric Multi-Agent Engine) —— 主流水线编排。

本模块实例化三个核心模块（Extractor → Analyzer → Reviewer），
并通过强类型 Pydantic 数据模型严格按顺序传递上下文，完成完整的
数据提取 → 分布漂移检测 → 脚本审计与执行 流水线。

运行方式：
    python main.py

环境要求：
    - Python 3.9+
    - pydantic >= 2.0
    - numpy
    - 可选: fiftyone, torch（缺失时自动降级到 Mock 模式）
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from schemas import DataSliceContext, DriftReport, ReviewDecision
from core.extractor import Extractor
from core.analyzer import Analyzer
from core.reviewer import Reviewer


# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    配置全局日志格式与级别。

    Args:
        level: 日志级别，默认为 INFO。

    Returns:
        配置好的根 logger。
    """
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # 避免重复添加 handler
    if not root_logger.handlers:
        root_logger.addHandler(handler)

    return root_logger


# ---------------------------------------------------------------------------
# 流水线编排
# ---------------------------------------------------------------------------
def run_pipeline(
    mock_sample_count: int = 10,
    dry_run: bool = True,
) -> ReviewDecision:
    """
    执行完整的多智能体可视分析流水线。

    流程顺序（严格线性）：
    1. Extractor.extract() → DataSliceContext
    2. Analyzer.analyze(ctx) → DriftReport
    3. Reviewer.generate_script(report) → str
    4. Reviewer.execute(script) → ReviewDecision

    Args:
        mock_sample_count: Mock 模式下生成的样本数量。
        dry_run: 是否为 Mock 执行模式（不实际连接 FiftyOne）。

    Returns:
        ReviewDecision: 最终的审计决策对象。
    """
    logger = logging.getLogger("pipeline")

    logger.info("=" * 70)
    logger.info("多智能体可视分析引擎启动")
    logger.info("=" * 70)

    # ------------------------------------------------------------------
    # 阶段 1: 感知 (Extraction)
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("▶ 阶段 1/4: 感知模块 (Extractor) —— 样本提取")
    logger.info("-" * 50)

    extractor = Extractor(mock_sample_count=mock_sample_count)
    ctx: DataSliceContext = extractor.extract()

    logger.info("  数据来源: %s", ctx.source)
    logger.info("  样本总数: %d", ctx.total_count)
    logger.info("  提取时间: %s", ctx.extraction_timestamp)
    logger.info("  运行模式: %s", extractor.mode)

    # 展示前 3 个样本的摘要
    for i, record in enumerate(ctx.sample_records[:3]):
        emb_preview = record.embedding[:5]
        emb_str = ", ".join(f"{v:.3f}" for v in emb_preview)
        logger.info(
            "  样本[%d]: id=%s | label=%-8s | emb=[%s ...]",
            i,
            record.image_id[:8],
            record.label,
            emb_str,
        )
    if ctx.total_count > 3:
        logger.info("  ... (省略其余 %d 个样本)", ctx.total_count - 3)

    # ------------------------------------------------------------------
    # 阶段 2: 推理 (Analysis)
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("▶ 阶段 2/4: 推理模块 (Analyzer) —— 分布漂移检测")
    logger.info("-" * 50)

    analyzer = Analyzer()
    report: DriftReport = analyzer.analyze(ctx)

    logger.info("  分析模式: %s", report.analysis_mode)
    logger.info("  运行模式: %s", analyzer.mode)
    logger.info("  均值距离: %.6f", report.mean_distance)
    logger.info("  漂移阈值: %.6f", report.threshold)
    logger.info("  漂移样本数: %d", len(report.drift_samples))

    for sample in report.drift_samples:
        logger.info(
            "  ⚠ 漂移样本: id=%s | score=%.6f | reason=%s",
            sample.image_id[:8],
            sample.drift_score,
            sample.reason,
        )

    # ------------------------------------------------------------------
    # 阶段 3: 脚本生成
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("▶ 阶段 3/4: 审计模块 (Reviewer) —— 脚本生成")
    logger.info("-" * 50)

    reviewer = Reviewer(dry_run=dry_run)
    script: str = reviewer.generate_script(report)

    logger.info("  脚本长度: %d 字符", len(script))
    logger.info("  Dry-Run 模式: %s", dry_run)

    # ------------------------------------------------------------------
    # 阶段 4: AST 审计与执行
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("▶ 阶段 4/4: 审计模块 (Reviewer) —— AST 安全审计与执行")
    logger.info("-" * 50)

    decision: ReviewDecision = reviewer.execute(script)

    logger.info("  AST 检查通过: %s", decision.ast_check_passed)
    logger.info("  AST 问题数: %d", len(decision.ast_issues))
    for issue in decision.ast_issues:
        logger.warning("  ✗ %s", issue)
    logger.info("  脚本已执行: %s", decision.executed)
    if decision.execution_log:
        logger.info("  执行日志: %s", decision.execution_log)

    # ------------------------------------------------------------------
    # 流水线总结
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("=" * 70)
    logger.info("流水线执行完成")
    logger.info(
        "  提取模式: %s → 分析模式: %s → 审计结果: %s",
        ctx.source,
        report.analysis_mode,
        "PASS" if decision.ast_check_passed else "FAIL",
    )
    logger.info("=" * 70)

    return decision


# ---------------------------------------------------------------------------
# 入口点
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    setup_logging(level=logging.INFO)
    result = run_pipeline(mock_sample_count=10, dry_run=True)

    # 退出码：AST 检查不通过时返回 1
    sys.exit(0 if result.ast_check_passed else 1)
