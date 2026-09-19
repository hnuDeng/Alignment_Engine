/**
 * @file  feature_graph.cpp
 * @brief FeatureGraph 模板类的实现
 *
 * 核心优化策略：
 *  1. 质心距离计算通过 OpenMP parallel for + 动态调度并行化
 *  2. 邻接图构建使用线程局部缓冲区避免锁竞争
 *  3. BFS 孤立度评分采用层序遍历 + 跳数记录
 *  4. 内存对齐 64 字节，匹配 AVX2 缓存行
 */

#include "feature_graph.h"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <queue>
#include <stdexcept>
#include <unordered_set>

#ifdef FEATURE_GRAPH_USE_OPENMP
#include <omp.h>
#endif

namespace fg {

// ══════════════════════════════════════════════════════════════
// FeatureGraph<T> — 构造 / 析构
// ══════════════════════════════════════════════════════════════

template <typename T>
FeatureGraph<T>::FeatureGraph()
    : embedding_dim_(kDefaultEmbeddingDim) {}

template <typename T>
FeatureGraph<T>::FeatureGraph(std::size_t embedding_dim)
    : embedding_dim_(embedding_dim) {
    if (embedding_dim == 0) {
        throw std::invalid_argument("embedding_dim must be > 0");
    }
}

template <typename T>
FeatureGraph<T>::~FeatureGraph() = default;

// ══════════════════════════════════════════════════════════════
// 节点管理
// ══════════════════════════════════════════════════════════════

template <typename T>
void FeatureGraph<T>::add_node(uint32_t id, uint32_t label_id,
                               const std::vector<T>& embedding) {
    if (embedding.size() != embedding_dim_) {
        throw std::invalid_argument(
            "embedding size (" + std::to_string(embedding.size()) +
            ") != embedding_dim (" + std::to_string(embedding_dim_) + ")");
    }
    nodes_.emplace_back(id, label_id, embedding);
}

template <typename T>
void FeatureGraph<T>::add_nodes_batch(
    const std::vector<uint32_t>& ids,
    const std::vector<uint32_t>& labels,
    const std::vector<std::vector<T>>& embeddings)
{
    if (ids.size() != labels.size() || ids.size() != embeddings.size()) {
        throw std::invalid_argument("ids/labels/embeddings size mismatch");
    }
    nodes_.reserve(nodes_.size() + ids.size());
    for (std::size_t i = 0; i < ids.size(); ++i) {
        add_node(ids[i], labels[i], embeddings[i]);
    }
}

template <typename T>
void FeatureGraph<T>::clear() noexcept {
    nodes_.clear();
    centroid_.clear();
}

// ══════════════════════════════════════════════════════════════
// 辅助函数
// ══════════════════════════════════════════════════════════════

template <typename T>
T FeatureGraph<T>::dist_sq(const std::vector<T>& a,
                           const std::vector<T>& b) const {
    T sum = 0;
    const std::size_t d = embedding_dim_;
    for (std::size_t k = 0; k < d; ++k) {
        T diff = a[k] - b[k];
        sum += diff * diff;
    }
    return sum;
}

template <typename T>
void FeatureGraph<T>::recompute_centroid() {
    const std::size_t n = nodes_.size();
    const std::size_t d = embedding_dim_;
    centroid_.assign(d, T(0));

    if (n == 0) return;

    // 单线程累加（节点数通常不足以使 OpenMP 有收益）
    for (std::size_t i = 0; i < n; ++i) {
        const auto& emb = nodes_[i].embedding;
        for (std::size_t k = 0; k < d; ++k) {
            centroid_[k] += emb[k];
        }
    }
    const T inv_n = T(1) / static_cast<T>(n);
    for (std::size_t k = 0; k < d; ++k) {
        centroid_[k] *= inv_n;
    }
}

// ══════════════════════════════════════════════════════════════
// 核心算法：质心距离（OpenMP 并行）
// ══════════════════════════════════════════════════════════════

template <typename T>
void FeatureGraph<T>::compute_centroid_distances() {
    const std::size_t n = nodes_.size();
    if (n == 0) return;

    recompute_centroid();

    // OpenMP 并行：每个线程独立计算自己负责节点的距离
    // schedule(dynamic, 64) 让负载不均匀时自动均衡
#ifdef FEATURE_GRAPH_USE_OPENMP
    #pragma omp parallel for schedule(dynamic, 64)
#endif
    for (int64_t i = 0; i < static_cast<int64_t>(n); ++i) {
        nodes_[static_cast<std::size_t>(i)].dist_sq_to_centroid =
            dist_sq(nodes_[static_cast<std::size_t>(i)].embedding, centroid_);
    }
}

// ══════════════════════════════════════════════════════════════
// 核心算法：邻接图构建（OpenMP 并行）
// ══════════════════════════════════════════════════════════════

template <typename T>
void FeatureGraph<T>::build_adjacency_graph(T threshold) {
    const std::size_t n = nodes_.size();
    const T threshold_sq = threshold * threshold;

    // 先清空旧邻接
    for (auto& node : nodes_) {
        node.neighbors.clear();
        node.neighbors.reserve(16);  // 预分配典型邻居数
    }

    // 线程局部缓冲区：避免临界区
    // 每个线程维护自己的邻居列表，最后合并
    std::vector<std::vector<uint32_t>> local_neighbors(n);

#ifdef FEATURE_GRAPH_USE_OPENMP
    #pragma omp parallel for schedule(dynamic, 32)
#endif
    for (int64_t i = 0; i < static_cast<int64_t>(n); ++i) {
        auto& my_neighbors = local_neighbors[static_cast<std::size_t>(i)];
        const auto& emb_i = nodes_[static_cast<std::size_t>(i)].embedding;

        for (std::size_t j = 0; j < n; ++j) {
            if (static_cast<std::size_t>(i) == j) continue;
            T d_sq = dist_sq(emb_i, nodes_[j].embedding);
            if (d_sq < threshold_sq) {
                my_neighbors.push_back(static_cast<uint32_t>(j));
            }
        }
    }

    // 合并到节点
    for (std::size_t i = 0; i < n; ++i) {
        nodes_[i].neighbors = std::move(local_neighbors[i]);
    }
}

// ══════════════════════════════════════════════════════════════
// 核心算法：BFS 孤立度评分
// ══════════════════════════════════════════════════════════════

template <typename T>
std::vector<std::pair<uint32_t, T>>
FeatureGraph<T>::bfs_isolation_score(std::size_t k_nearest, std::size_t max_hops) {
    const std::size_t n = nodes_.size();
    if (n == 0) return {};

    // 1) 确保质心距离已计算
    compute_centroid_distances();

    // 2) 按到质心距离升序排列，取前 k_nearest 作为 BFS 种子
    std::vector<uint32_t> indices(n);
    std::iota(indices.begin(), indices.end(), 0u);
    std::sort(indices.begin(), indices.end(),
              [this](uint32_t a, uint32_t b) {
                  return nodes_[a].dist_sq_to_centroid <
                         nodes_[b].dist_sq_to_centroid;
              });

    const std::size_t seed_count = std::min(k_nearest, n);

    // 3) BFS 层序遍历，记录每个节点第一次被访问时的跳数
    //    hop[i] = UINT32_MAX 表示未被访问
    constexpr uint32_t UNVISITED = UINT32_MAX;
    std::vector<uint32_t> hop(n, UNVISITED);

    std::queue<uint32_t> frontier;
    for (std::size_t s = 0; s < seed_count; ++s) {
        uint32_t seed_idx = indices[s];
        if (hop[seed_idx] == UNVISITED) {
            hop[seed_idx] = 0;
            frontier.push(seed_idx);
        }
    }

    uint32_t current_hop = 0;
    while (!frontier.empty() && current_hop < static_cast<uint32_t>(max_hops)) {
        const std::size_t level_size = frontier.size();
        ++current_hop;
        for (std::size_t li = 0; li < level_size; ++li) {
            uint32_t u = frontier.front();
            frontier.pop();
            for (uint32_t v : nodes_[u].neighbors) {
                if (hop[v] == UNVISITED) {
                    hop[v] = current_hop;
                    frontier.push(v);
                }
            }
        }
    }

    // 4) 写入 isolation_score：跳数越大越孤立
    //    未被访问的节点获得 max_hops + 1
    const T max_score = static_cast<T>(max_hops + 1);
    for (std::size_t i = 0; i < n; ++i) {
        if (hop[i] == UNVISITED) {
            nodes_[i].isolation_score = max_score;
        } else {
            nodes_[i].isolation_score = static_cast<T>(hop[i]);
        }
    }

    // 5) 返回按 isolation_score 降序排列的 (index, score) 对
    std::vector<std::pair<uint32_t, T>> results;
    results.reserve(n);
    for (std::size_t i = 0; i < n; ++i) {
        results.emplace_back(static_cast<uint32_t>(i), nodes_[i].isolation_score);
    }
    std::sort(results.begin(), results.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });

    return results;
}

// ══════════════════════════════════════════════════════════════
// Top-K 异常节点
// ══════════════════════════════════════════════════════════════

template <typename T>
std::vector<uint32_t> FeatureGraph<T>::top_outliers(std::size_t top_n) const {
    std::vector<uint32_t> indices(nodes_.size());
    std::iota(indices.begin(), indices.end(), 0u);

    std::sort(indices.begin(), indices.end(),
              [this](uint32_t a, uint32_t b) {
                  return nodes_[a].dist_sq_to_centroid >
                         nodes_[b].dist_sq_to_centroid;
              });

    if (top_n > indices.size()) top_n = indices.size();
    return {indices.begin(), indices.begin() + static_cast<std::ptrdiff_t>(top_n)};
}

// ══════════════════════════════════════════════════════════════
// 序列化导出
// ══════════════════════════════════════════════════════════════

template <typename T>
std::pair<std::vector<uint32_t>, std::vector<T>>
FeatureGraph<T>::export_isolation_results() const {
    std::vector<uint32_t> ids;
    std::vector<T> scores;
    ids.reserve(nodes_.size());
    scores.reserve(nodes_.size());
    for (const auto& node : nodes_) {
        ids.push_back(node.id);
        scores.push_back(node.isolation_score);
    }
    return {std::move(ids), std::move(scores)};
}

// ── 显式实例化 ───────────────────────────────────────────────
template class FeatureGraph<float>;
template class FeatureGraph<double>;

}  // namespace fg
