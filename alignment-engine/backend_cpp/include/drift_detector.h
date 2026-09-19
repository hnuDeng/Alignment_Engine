/**
 * @file  drift_detector.h
 * @brief 基于 FeatureGraph 的分布漂移检测器
 *
 * 封装 Extractor → FeatureGraph → DriftReport 的完整计算流程，
 * 作为 pybind11 暴露给 Python 的高层 API。
 */

#pragma once

#include "feature_graph.h"
#include <cstdint>
#include <string>
#include <vector>

namespace fg {

/**
 * @brief 漂移检测结果
 */
struct DriftResult {
    /// 异常样本 ID 列表
    std::vector<uint32_t> outlier_ids;
    /// 对应的孤立度分数
    std::vector<double>   outlier_scores;
    /// 对应的漂移原因描述
    std::vector<std::string> outlier_reasons;
    /// 质心到各节点的平均距离
    double mean_distance;
    /// 漂移阈值（基于 sigma 倍标准差）
    double threshold;
};

/**
 * @brief 分布漂移检测器
 *
 * 高层 API，串联 FeatureGraph 的各步骤：
 *  1. 构建图 + 添加节点
 *  2. 计算质心距离
 *  3. 构建邻接图
 *  4. BFS 孤立度评分
 *  5. 选取 Top-K 异常样本
 *
 * 线程安全：非线程安全，单线程使用。
 */
class DriftDetector {
public:
    /**
     * @param embedding_dim  嵌入维度
     * @param sigma          阈值倍数（均值 + sigma * 标准差）
     * @param max_outliers   最多报告的异常样本数
     * @param k_nearest      BFS 种子节点数
     * @param max_bfs_hops   BFS 最大深度
     * @param adjacency_threshold  邻接图距离阈值
     */
    DriftDetector(
        std::size_t embedding_dim = 128,
        double sigma              = 2.0,
        std::size_t max_outliers  = 3,
        std::size_t k_nearest     = 5,
        std::size_t max_bfs_hops  = 10,
        double adjacency_threshold = 15.0
    );

    ~DriftDetector();

    // ── 禁止拷贝 ─────────────────────────────────────────────
    DriftDetector(const DriftDetector&)            = delete;
    DriftDetector& operator=(const DriftDetector&) = delete;
    DriftDetector(DriftDetector&&) noexcept         = default;
    DriftDetector& operator=(DriftDetector&&) noexcept = default;

    /**
     * @brief 从扁平化的嵌入矩阵检测漂移
     *
     * @param ids          样本 ID 数组（长度 N）
     * @param labels       标签 ID 数组（长度 N）
     * @param flat_embeddings  扁平嵌入（长度 N * embedding_dim，行主序）
     * @return DriftResult
     */
    DriftResult detect(
        const std::vector<uint32_t>& ids,
        const std::vector<uint32_t>& labels,
        const std::vector<double>&   flat_embeddings
    );

    /**
     * @brief 从嵌入向量数组检测漂移
     */
    DriftResult detect(
        const std::vector<uint32_t>& ids,
        const std::vector<uint32_t>& labels,
        const std::vector<std::vector<double>>& embeddings
    );

    /** @brief 获取内部 FeatureGraph 的只读引用（调试用） */
    [[nodiscard]] const FeatureGraph<double>& graph() const { return graph_; }

private:
    FeatureGraph<double> graph_;
    double       sigma_;
    std::size_t  max_outliers_;
    std::size_t  k_nearest_;
    std::size_t  max_bfs_hops_;
    double       adjacency_threshold_;
};

}  // namespace fg
