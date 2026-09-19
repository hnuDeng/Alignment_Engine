/**
 * @file  graph_search.cpp
 * @brief GraphSearch 实现 —— BFS 长尾孤立检测 + DP 最短分布路径
 *
 * 并发安全设计：
 *  - compute_distance_matrix: 外层 for-i OpenMP parallel，内层只写上三角
 *    通过 #pragma omp atomic write 同步 dist(j,i) = dist(i,j)
 *  - build_graph: 每个线程写入独立的线程局部邻接缓冲区，最后合并
 *  - dp_shortest_distribution_path: #pragma omp critical 保护松弛写入
 */

#include "graph_search.h"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <queue>
#include <stdexcept>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace gs {

// ══════════════════════════════════════════════════════════════
// 构造 / 析构
// ══════════════════════════════════════════════════════════════

GraphSearch::GraphSearch(std::size_t embedding_dim) : dim_(embedding_dim) {
    if (dim_ == 0) throw std::invalid_argument("embedding_dim must be > 0");
}

GraphSearch::~GraphSearch() = default;

// ══════════════════════════════════════════════════════════════
// 节点管理
// ══════════════════════════════════════════════════════════════

void GraphSearch::add_node(uint32_t id, uint32_t label_id,
                           const std::vector<double>& embedding) {
    if (embedding.size() != dim_) {
        throw std::invalid_argument(
            "embedding size " + std::to_string(embedding.size()) +
            " != dim " + std::to_string(dim_));
    }
    nodes_.emplace_back(id, label_id, embedding);
}

void GraphSearch::add_nodes_batch(
    const std::vector<uint32_t>& ids,
    const std::vector<uint32_t>& labels,
    const std::vector<std::vector<double>>& embeddings)
{
    if (ids.size() != labels.size() || ids.size() != embeddings.size()) {
        throw std::invalid_argument("ids/labels/embeddings size mismatch");
    }
    nodes_.reserve(nodes_.size() + ids.size());
    for (std::size_t i = 0; i < ids.size(); ++i) {
        add_node(ids[i], labels[i], embeddings[i]);
    }
}

void GraphSearch::clear() noexcept {
    nodes_.clear();
    adj_.clear();
    edges_.clear();
    centroid_.clear();
}

// ══════════════════════════════════════════════════════════════
// 辅助
// ══════════════════════════════════════════════════════════════

double GraphSearch::dist_sq(const std::vector<double>& a,
                            const std::vector<double>& b) const {
    double sum = 0.0;
    for (std::size_t k = 0; k < dim_; ++k) {
        double d = a[k] - b[k];
        sum += d * d;
    }
    return sum;
}

void GraphSearch::recompute_centroid() {
    const std::size_t n = nodes_.size();
    centroid_.assign(dim_, 0.0);
    if (n == 0) return;

    for (std::size_t i = 0; i < n; ++i) {
        for (std::size_t k = 0; k < dim_; ++k) {
            centroid_[k] += nodes_[i].embedding[k];
        }
    }
    const double inv = 1.0 / static_cast<double>(n);
    for (std::size_t k = 0; k < dim_; ++k) {
        centroid_[k] *= inv;
    }
}

// ══════════════════════════════════════════════════════════════
// 核心算法 1：并行距离矩阵
//
// 外层 for-i OpenMP parallel schedule(dynamic,64)
// 内层只计算 j > i 上三角，通过 omp atomic write 保证 dist(j,i) 写入无竞争
// ══════════════════════════════════════════════════════════════

void GraphSearch::compute_distance_matrix(std::vector<double>& dist_matrix) const {
    const std::size_t n = nodes_.size();
    dist_matrix.assign(n * n, 0.0);
    if (n <= 1) return;

    // 更新质心
    const_cast<GraphSearch*>(this)->recompute_centroid();

    // 写入质心距离到每个节点
    const_cast<GraphSearch*>(this)->centroid_ = centroid_;
    for (std::size_t i = 0; i < n; ++i) {
        const_cast<GraphSearch*>(this)->nodes_[i].dist_sq_to_centroid =
            dist_sq(nodes_[i].embedding, centroid_);
    }

    // 全对距离矩阵：上三角并行计算，atomic 写入镜像
#ifdef _OPENMP
    #pragma omp parallel for schedule(dynamic, 64)
#endif
    for (int64_t i = 0; i < static_cast<int64_t>(n); ++i) {
        const auto& emb_i = nodes_[static_cast<std::size_t>(i)].embedding;
        for (std::size_t j = static_cast<std::size_t>(i) + 1; j < n; ++j) {
            double d = std::sqrt(dist_sq(emb_i, nodes_[j].embedding));
            dist_matrix[static_cast<std::size_t>(i) * n + j] = d;
            // atomic write 镜像值，避免数据竞争
#ifdef _OPENMP
            #pragma omp atomic write
#endif
            dist_matrix[j * n + static_cast<std::size_t>(i)] = d;
        }
    }
}

// ══════════════════════════════════════════════════════════════
// 核心算法 2：图构建
//
// 每个线程写入线程局部缓冲区，结束后合并（无锁设计）
// ══════════════════════════════════════════════════════════════

void GraphSearch::build_graph(double threshold, const std::vector<double>& dist_matrix) {
    const std::size_t n = nodes_.size();
    adj_.clear();
    adj_.resize(n);
    edges_.clear();
    edges_.reserve(n * 16);  // 预估平均度 16

    // 线程局部缓冲区：避免临界区
    std::vector<std::vector<uint32_t>> local_adj(n);

#ifdef _OPENMP
    #pragma omp parallel for schedule(dynamic, 32)
#endif
    for (int64_t i = 0; i < static_cast<int64_t>(n); ++i) {
        auto& my_adj = local_adj[static_cast<std::size_t>(i)];
        for (std::size_t j = static_cast<std::size_t>(i) + 1; j < n; ++j) {
            double d = dist_matrix[static_cast<std::size_t>(i) * n + j];
            if (d < threshold) {
                my_adj.push_back(static_cast<uint32_t>(j));
            }
        }
    }

    // 合并：构建无向邻接表 + SoA 边列表
    for (std::size_t i = 0; i < n; ++i) {
        for (uint32_t j : local_adj[i]) {
            adj_[i].push_back(j);
            adj_[j].push_back(static_cast<uint32_t>(i));
            edges_.push_back(static_cast<uint32_t>(i), j,
                             dist_matrix[i * n + j]);
        }
    }
}

// ══════════════════════════════════════════════════════════════
// 核心算法 3：BFS 长尾孤立检测
//
// 从距质心最近的 k_seeds 个节点出发层序 BFS
// hop[i] = 首次被访问的跳数，越大越孤立
// ══════════════════════════════════════════════════════════════

std::vector<std::pair<uint32_t, double>>
GraphSearch::bfs_longtail_isolation(std::size_t k_seeds, std::size_t max_hops) {
    const std::size_t n = nodes_.size();
    if (n == 0) return {};

    // 确保质心距离已计算
    recompute_centroid();
    for (std::size_t i = 0; i < n; ++i) {
        nodes_[i].dist_sq_to_centroid = dist_sq(nodes_[i].embedding, centroid_);
    }

    // 按质心距离升序排列，取前 k_seeds 作为种子
    std::vector<uint32_t> order(n);
    std::iota(order.begin(), order.end(), 0u);
    std::sort(order.begin(), order.end(),
              [this](uint32_t a, uint32_t b) {
                  return nodes_[a].dist_sq_to_centroid < nodes_[b].dist_sq_to_centroid;
              });
    const std::size_t seed_count = std::min(k_seeds, n);

    // BFS 层序遍历
    constexpr int UNVISITED = -1;
    std::vector<int> hop(n, UNVISITED);
    std::queue<uint32_t> frontier;

    for (std::size_t s = 0; s < seed_count; ++s) {
        uint32_t seed = order[s];
        if (hop[seed] == UNVISITED) {
            hop[seed] = 0;
            frontier.push(seed);
        }
    }

    int current = 0;
    while (!frontier.empty() && static_cast<std::size_t>(current) < max_hops) {
        const std::size_t level_size = frontier.size();
        ++current;
        for (std::size_t li = 0; li < level_size; ++li) {
            uint32_t u = frontier.front();
            frontier.pop();
            for (uint32_t v : adj_[u]) {
                if (hop[v] == UNVISITED) {
                    hop[v] = current;
                    frontier.push(v);
                }
            }
        }
    }

    // 写入 isolation_score
    const double max_score = static_cast<double>(max_hops + 1);
    for (std::size_t i = 0; i < n; ++i) {
        nodes_[i].isolation_score = (hop[i] == UNVISITED)
            ? max_score : static_cast<double>(hop[i]);
    }

    // 排序输出
    std::vector<std::pair<uint32_t, double>> results;
    results.reserve(n);
    for (std::size_t i = 0; i < n; ++i) {
        results.emplace_back(static_cast<uint32_t>(i), nodes_[i].isolation_score);
    }
    std::sort(results.begin(), results.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });
    return results;
}

// ══════════════════════════════════════════════════════════════
// 核心算法 4：DP 最短分布路径（Bellman-Ford 并行松弛）
//
// 从多个种子节点出发，计算到所有可达节点的最短加权路径。
// 每轮对所有边并行松弛，通过 #pragma omp critical 保护写入。
// ══════════════════════════════════════════════════════════════

std::pair<std::vector<double>, std::vector<int>>
GraphSearch::dp_shortest_distribution_path(
    const std::vector<uint32_t>& source_indices,
    std::size_t max_iterations)
{
    const std::size_t n = nodes_.size();
    const std::size_t m = edges_.size();

    // 默认迭代次数 = min(N-1, 实际节点数)
    if (max_iterations == 0) {
        max_iterations = (n > 1) ? n - 1 : 1;
    }

    // 初始化
    std::vector<double> dist(n, kInfDist);
    std::vector<int>    hops(n, -1);

    for (uint32_t s : source_indices) {
        if (s < n) {
            dist[s] = 0.0;
            hops[s] = 0;
        }
    }

    // Bellman-Ford 松弛（OpenMP parallel）
    for (std::size_t iter = 0; iter < max_iterations; ++iter) {
        bool updated = false;

#ifdef _OPENMP
        #pragma omp parallel for schedule(dynamic, 256) reduction(|:updated)
#endif
        for (int64_t ei = 0; ei < static_cast<int64_t>(m); ++ei) {
            auto idx = static_cast<std::size_t>(ei);
            uint32_t u = edges_.src[idx];
            uint32_t v = edges_.dst[idx];
            double w   = edges_.weight[idx];

            // 松弛 u -> v
            if (dist[u] < kInfDist && dist[u] + w < dist[v]) {
#ifdef _OPENMP
                #pragma omp critical
#endif
                {
                    if (dist[u] + w < dist[v]) {
                        dist[v] = dist[u] + w;
                        hops[v] = hops[u] + 1;
                        updated = true;
                    }
                }
            }

            // 松弛 v -> u（无向图）
            if (dist[v] < kInfDist && dist[v] + w < dist[u]) {
#ifdef _OPENMP
                #pragma omp critical
#endif
                {
                    if (dist[v] + w < dist[u]) {
                        dist[u] = dist[v] + w;
                        hops[u] = hops[v] + 1;
                        updated = true;
                    }
                }
            }
        }

        if (!updated) break;  // 提前收敛
    }

    // 写入节点
    for (std::size_t i = 0; i < n; ++i) {
        nodes_[i].shortest_path_hop = hops[i];
    }

    return {std::move(dist), std::move(hops)};
}

// ══════════════════════════════════════════════════════════════
// 导出
// ══════════════════════════════════════════════════════════════

std::vector<uint32_t> GraphSearch::top_k_isolated(std::size_t k) const {
    std::vector<uint32_t> idx(nodes_.size());
    std::iota(idx.begin(), idx.end(), 0u);
    std::sort(idx.begin(), idx.end(),
              [this](uint32_t a, uint32_t b) {
                  return nodes_[a].isolation_score > nodes_[b].isolation_score;
              });
    if (k > idx.size()) k = idx.size();
    return {idx.begin(), idx.begin() + static_cast<std::ptrdiff_t>(k)};
}

std::pair<std::vector<uint32_t>, std::vector<double>>
GraphSearch::export_isolation_scores() const {
    std::vector<uint32_t> ids;
    std::vector<double> scores;
    ids.reserve(nodes_.size());
    scores.reserve(nodes_.size());
    for (const auto& nd : nodes_) {
        ids.push_back(nd.id);
        scores.push_back(nd.isolation_score);
    }
    return {std::move(ids), std::move(scores)};
}

}  // namespace gs
