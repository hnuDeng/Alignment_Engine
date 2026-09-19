/**
 * @file  graph_search.h
 * @brief 高维特征空间无向图 —— BFS 长尾孤立检测 + DP 最短分布路径
 *
 * 核心设计：
 *  1. FeatureNode: 64 字节对齐，嵌入向量独立堆分配
 *  2. 邻接表使用 SoA (Structure-of-Arrays) 布局提升缓存命中率
 *  3. 全部距离矩阵计算通过 OpenMP parallel for + #pragma omp atomic 避免竞争
 *  4. DP 最短路径采用松弛迭代（Bellman-Ford 变体），可并行松弛
 *  5. BFS 孤立检测：从质心最近 K 邻居出发层序遍历，跳数 = 孤立度
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace gs {

// ── 常量 ──────────────────────────────────────────────────────
inline constexpr std::size_t kDefaultDim   = 128;
inline constexpr std::size_t kCacheLine    = 64;
inline constexpr double      kInfDist      = std::numeric_limits<double>::infinity();

/**
 * @brief 64 字节对齐的特征图节点
 *
 * 字段布局优化：
 *  - 高频访问字段 (id, label_id, dist_sq) 在前 16 字节
 *  - 嵌入向量独立堆分配，避免结构体膨胀导致缓存抖动
 */
struct alignas(kCacheLine) FeatureNode {
    uint32_t id;                     ///< 样本唯一 ID
    uint32_t label_id;               ///< 类别标签 ID
    double   dist_sq_to_centroid;    ///< 到质心的欧氏距离平方
    double   isolation_score;        ///< BFS 孤立度分数
    int      shortest_path_hop;      ///< DP 最短路径跳数（从种子集出发）

    std::vector<double> embedding;   ///< 高维嵌入向量（堆分配）

    FeatureNode()
        : id(0), label_id(0),
          dist_sq_to_centroid(0.0), isolation_score(0.0),
          shortest_path_hop(-1) {}

    FeatureNode(uint32_t node_id, uint32_t lbl, const std::vector<double>& emb)
        : id(node_id), label_id(lbl),
          dist_sq_to_centroid(0.0), isolation_score(0.0),
          shortest_path_hop(-1), embedding(emb) {}
};

/**
 * @brief 边（用于最短路径计算）
 *
 * 存储源节点、目标节点和权重（欧氏距离），
 * SoA 风格：边列表按 (src, dst, weight) 平行数组存储。
 */
struct EdgeList {
    std::vector<uint32_t> src;       ///< 源节点索引
    std::vector<uint32_t> dst;       ///< 目标节点索引
    std::vector<double>   weight;    ///< 边权重（欧氏距离）

    void reserve(std::size_t n) {
        src.reserve(n);
        dst.reserve(n);
        weight.reserve(n);
    }

    void push_back(uint32_t s, uint32_t d, double w) {
        src.push_back(s);
        dst.push_back(d);
        weight.push_back(w);
    }

    [[nodiscard]] std::size_t size() const noexcept { return src.size(); }
    void clear() { src.clear(); dst.clear(); weight.clear(); }
};

/**
 * @brief 高维特征空间图搜索引擎
 *
 * 核心方法：
 *  - compute_distance_matrix(): 并行计算全对欧氏距离（OpenMP parallel for + atomic）
 *  - build_graph(): 基于距离阈值构建无向邻接表 + 边列表
 *  - bfs_longtail_isolation(): BFS 检测长尾孤立节点
 *  - dp_shortest_distribution_path(): DP 计算最短分布路径
 */
class GraphSearch {
public:
    explicit GraphSearch(std::size_t embedding_dim = kDefaultDim);
    ~GraphSearch();

    GraphSearch(const GraphSearch&)            = delete;
    GraphSearch& operator=(const GraphSearch&) = delete;
    GraphSearch(GraphSearch&&) noexcept         = default;
    GraphSearch& operator=(GraphSearch&&) noexcept = default;

    // ── 节点管理 ─────────────────────────────────────────────
    void add_node(uint32_t id, uint32_t label_id, const std::vector<double>& embedding);
    void add_nodes_batch(const std::vector<uint32_t>& ids,
                         const std::vector<uint32_t>& labels,
                         const std::vector<std::vector<double>>& embeddings);
    [[nodiscard]] std::size_t size() const noexcept { return nodes_.size(); }
    [[nodiscard]] std::size_t embedding_dim() const noexcept { return dim_; }
    [[nodiscard]] const FeatureNode& node(std::size_t i) const { return nodes_.at(i); }
    void clear() noexcept;

    // ── 核心算法 1：并行距离矩阵 ────────────────────────────
    /**
     * @brief 计算 N×N 对称欧氏距离矩阵
     *
     * 并行策略：
     *  - 外层 for-i 通过 OpenMP parallel for 并行
     *  - 内层 for-j 只计算 j > i（上三角），通过 #pragma omp atomic write
     *    写入 dist(i,j) 和 dist(j,i)，保证无数据竞争
     *
     * @param dist_matrix  输出 N×N 矩阵（行主序，调用者预分配 N*N）
     */
    void compute_distance_matrix(std::vector<double>& dist_matrix) const;

    // ── 核心算法 2：图构建 ──────────────────────────────────
    /**
     * @brief 基于欧氏距离阈值构建无向加权图
     *
     * @param threshold   距离阈值（非平方）
     * @param dist_matrix 距离矩阵（由 compute_distance_matrix 填充）
     */
    void build_graph(double threshold, const std::vector<double>& dist_matrix);

    // ── 核心算法 3：BFS 长尾孤立检测 ────────────────────────
    /**
     * @brief 从距质心最近的 K 个种子节点出发层序 BFS
     *
     * 每个节点记录首次被访问时的跳数 hop。
     * hop 越大 → 节点越孤立（长尾特征）。
     * 未被访问的节点获得 max_hops + 1（最大孤立度）。
     *
     * @param k_seeds    种子节点数
     * @param max_hops   最大 BFS 深度
     * @return           按 isolation_score 降序排列的 (node_index, score) 对
     */
    std::vector<std::pair<uint32_t, double>>
    bfs_longtail_isolation(std::size_t k_seeds, std::size_t max_hops);

    // ── 核心算法 4：DP 最短分布路径 ────────────────────────
    /**
     * @brief 计算从种子节点集到所有节点的最短加权路径
     *
     * 采用 Bellman-Ford 变体的并行松弛：
     *  - 初始化种子节点距离 = 0
     *  - 迭代 N-1 轮，每轮对所有边并行松弛
     *  - 松弛操作通过 #pragma omp critical 保护（写入共享 dist 数组）
     *
     * @param source_indices  种子节点索引列表
     * @param max_iterations  最大松弛轮数
     * @return                (最短距离数组, 最短路径跳数数组)
     */
    std::pair<std::vector<double>, std::vector<int>>
    dp_shortest_distribution_path(
        const std::vector<uint32_t>& source_indices,
        std::size_t max_iterations = 0
    );

    // ── 导出 ─────────────────────────────────────────────────
    [[nodiscard]] std::vector<uint32_t> top_k_isolated(std::size_t k) const;
    [[nodiscard]] std::pair<std::vector<uint32_t>, std::vector<double>>
    export_isolation_scores() const;

    [[nodiscard]] const std::vector<std::vector<uint32_t>>& adjacency() const { return adj_; }
    [[nodiscard]] const EdgeList& edges() const { return edges_; }

private:
    std::size_t dim_;
    std::vector<FeatureNode> nodes_;
    std::vector<std::vector<uint32_t>> adj_;       ///< 邻接表
    EdgeList edges_;                                ///< SoA 边列表
    std::vector<double> centroid_;                  ///< 质心向量

    void recompute_centroid();
    [[nodiscard]] double dist_sq(const std::vector<double>& a,
                                 const std::vector<double>& b) const;
};

}  // namespace gs
