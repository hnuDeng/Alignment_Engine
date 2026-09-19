/**
 * @file  drift_detector.cpp
 * @brief DriftDetector 实现 —— 高层 API，串联 FeatureGraph 各步骤
 */

#include "drift_detector.h"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <sstream>

namespace fg {

// ══════════════════════════════════════════════════════════════
// 构造 / 析构
// ══════════════════════════════════════════════════════════════

DriftDetector::DriftDetector(
    std::size_t embedding_dim,
    double sigma,
    std::size_t max_outliers,
    std::size_t k_nearest,
    std::size_t max_bfs_hops,
    double adjacency_threshold)
    : graph_(embedding_dim),
      sigma_(sigma),
      max_outliers_(max_outliers),
      k_nearest_(k_nearest),
      max_bfs_hops_(max_bfs_hops),
      adjacency_threshold_(adjacency_threshold) {}

DriftDetector::~DriftDetector() = default;

// ══════════════════════════════════════════════════════════════
// 扁平矩阵接口
// ══════════════════════════════════════════════════════════════

DriftResult DriftDetector::detect(
    const std::vector<uint32_t>& ids,
    const std::vector<uint32_t>& labels,
    const std::vector<double>&   flat_embeddings)
{
    const std::size_t n = ids.size();
    const std::size_t d = graph_.embedding_dim();

    if (flat_embeddings.size() != n * d) {
        throw std::invalid_argument(
            "flat_embeddings size (" + std::to_string(flat_embeddings.size()) +
            ") != n * dim (" + std::to_string(n * d) + ")");
    }

    // 将扁平矩阵拆分为向量数组
    std::vector<std::vector<double>> embeddings(n, std::vector<double>(d));
    for (std::size_t i = 0; i < n; ++i) {
        std::copy_n(flat_embeddings.begin() + static_cast<std::ptrdiff_t>(i * d),
                    d, embeddings[i].begin());
    }

    return detect(ids, labels, embeddings);
}

// ══════════════════════════════════════════════════════════════
// 向量数组接口（主逻辑）
// ══════════════════════════════════════════════════════════════

DriftResult DriftDetector::detect(
    const std::vector<uint32_t>& ids,
    const std::vector<uint32_t>& labels,
    const std::vector<std::vector<double>>& embeddings)
{
    // 重建图
    graph_.clear();
    graph_.add_nodes_batch(ids, labels, embeddings);

    // Step 1: 质心距离（内部 OpenMP 并行）
    graph_.compute_centroid_distances();

    // Step 2: 邻接图构建
    graph_.build_adjacency_graph(static_cast<double>(adjacency_threshold_));

    // Step 3: BFS 孤立度评分
    auto bfs_results = graph_.bfs_isolation_score(k_nearest_, max_bfs_hops_);

    // Step 4: 统计距离分布，计算阈值
    const std::size_t n = graph_.size();
    double sum_dist = 0.0;
    std::vector<double> distances(n);
    for (std::size_t i = 0; i < n; ++i) {
        distances[i] = std::sqrt(static_cast<double>(
            graph_.node(i).dist_sq_to_centroid));
        sum_dist += distances[i];
    }

    double mean_dist = sum_dist / static_cast<double>(n);
    double var_sum   = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        double diff = distances[i] - mean_dist;
        var_sum += diff * diff;
    }
    double std_dist = std::sqrt(var_sum / static_cast<double>(n));
    double threshold = mean_dist + sigma_ * std_dist;

    // Step 5: 选取异常样本
    // 综合 BFS 孤立度分数 + 质心距离排序
    // 优先取 BFS 分数最高的（最孤立），相同分数时取距离最大的
    std::sort(bfs_results.begin(), bfs_results.end(),
              [&](const auto& a, const auto& b) {
                  if (a.second != b.second) return a.second > b.second;
                  return distances[a.first] > distances[b.first];
              });

    DriftResult result;
    result.mean_distance = mean_dist;
    result.threshold     = threshold;

    const std::size_t pick = std::min(max_outliers_, bfs_results.size());
    for (std::size_t i = 0; i < pick; ++i) {
        uint32_t node_idx = bfs_results[i].first;
        const auto& node  = graph_.node(node_idx);

        result.outlier_ids.push_back(node.id);
        result.outlier_scores.push_back(static_cast<double>(bfs_results[i].second));

        std::ostringstream oss;
        oss << "BFS isolation score=" << bfs_results[i].second
            << ", centroid distance=" << distances[node_idx]
            << " (threshold=" << threshold << ")"
            << ", label_id=" << node.label_id;
        result.outlier_reasons.push_back(oss.str());
    }

    return result;
}

}  // namespace fg
