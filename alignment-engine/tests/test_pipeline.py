"""
集成测试 —— 端到端流水线测试

覆盖范围：
- 完整 Extractor → Analyzer → Reviewer 流水线
- 数据在各节点间的正确流转
- Pydantic 数据契约的端到端一致性
- 各种边界情况下的流水线行为
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from schemas import DataSliceContext, DriftReport, ReviewDecision
from core.extractor import Extractor
from core.analyzer import Analyzer
from core.reviewer import Reviewer


class TestPipelineIntegration:
    """端到端流水线集成测试。"""

    def test_full_pipeline_dry_run(self) -> None:
        """完整的 Dry-Run 流水线应成功执行。"""
        # 阶段 1: 提取
        extractor = Extractor(mock_sample_count=10)
        ctx = extractor.extract()
        assert isinstance(ctx, DataSliceContext)
        assert ctx.total_count == 10

        # 阶段 2: 分析
        analyzer = Analyzer()
        report = analyzer.analyze(ctx)
        assert isinstance(report, DriftReport)
        assert len(report.drift_samples) >= 1

        # 阶段 3: 生成脚本
        reviewer = Reviewer(dry_run=True)
        script = reviewer.generate_script(report)
        assert len(script) > 0

        # 阶段 4: 审计与执行
        decision = reviewer.execute(script)
        assert isinstance(decision, ReviewDecision)
        assert decision.ast_check_passed is True
        assert decision.executed is True

    def test_full_pipeline_data_flow(self) -> None:
        """验证数据在各节点间的正确流转。"""
        extractor = Extractor(mock_sample_count=5)
        analyzer = Analyzer(sigma_multiplier=1.5)
        reviewer = Reviewer(dry_run=True)

        # 提取
        ctx = extractor.extract()
        assert ctx.source == "mock"

        # 分析：使用提取的数据
        report = analyzer.analyze(ctx)
        assert report.analysis_mode == "mock_numpy"

        # 审计：所有漂移 ID 应来自提取的样本
        extracted_ids = {r.image_id for r in ctx.sample_records}
        for drift_id in report.drift_sample_ids:
            assert drift_id in extracted_ids

        # 执行：脚本应包含所有漂移 ID
        script = reviewer.generate_script(report)
        for drift_id in report.drift_sample_ids:
            assert drift_id in script

    def test_pipeline_with_single_sample(self) -> None:
        """只有 1 个样本时流水线应正常工作。"""
        extractor = Extractor(mock_sample_count=1)
        analyzer = Analyzer(min_drift=1, max_drift=1)
        reviewer = Reviewer(dry_run=True)

        ctx = extractor.extract()
        report = analyzer.analyze(ctx)
        script = reviewer.generate_script(report)
        decision = reviewer.execute(script)

        assert decision.ast_check_passed is True
        assert decision.executed is True

    def test_pipeline_with_large_dataset(self) -> None:
        """大数据集（100 个样本）应正常处理。"""
        extractor = Extractor(mock_sample_count=100)
        analyzer = Analyzer()
        reviewer = Reviewer(dry_run=True)

        ctx = extractor.extract()
        report = analyzer.analyze(ctx)
        script = reviewer.generate_script(report)
        decision = reviewer.execute(script)

        assert ctx.total_count == 100
        assert decision.ast_check_passed is True

    def test_pipeline_preserves_immutability(self) -> None:
        """流水线中传递的 Pydantic 模型应保持不可变。"""
        extractor = Extractor(mock_sample_count=5)
        ctx = extractor.extract()

        with pytest.raises(Exception):
            ctx.source = "modified"  # type: ignore[misc]

        analyzer = Analyzer()
        report = analyzer.analyze(ctx)

        with pytest.raises(Exception):
            report.threshold = 999.0  # type: ignore[misc]


class TestPipelineMainFunction:
    """测试 main.py 中的 run_pipeline 函数。"""

    def test_run_pipeline_returns_decision(self) -> None:
        """run_pipeline 应返回 ReviewDecision。"""
        from main import run_pipeline

        decision = run_pipeline(mock_sample_count=5, dry_run=True)
        assert isinstance(decision, ReviewDecision)

    def test_run_pipeline_success_exit(self) -> None:
        """正常流水线应产生 ast_check_passed=True 的决策。"""
        from main import run_pipeline

        decision = run_pipeline(mock_sample_count=5, dry_run=True)
        assert decision.ast_check_passed is True
        assert decision.executed is True
