/**
 * @file  feature_graph.h
 * @brief 高维特征图数据结构与 BFS 异常节点检测器
 *
 * 设计要点：
 *  1. FeatureNode 使用 64 字节对齐，确保 SIMD / 缓存行友好
 *  2. FeatureGraph 管理节点数组并提供基于 BFS 的"最孤立样本"搜索
 *  3. 所有距离计算均通过 OpenMP 并行化（受 FEATURE_GRAPH_USE_OPENMP 宏控制）
 *  4. 支持 float32 / float64 双精度模板参数，通过编译期策略选择
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace fg {

// ── 常量 ──────────────────────────────────────────────────────
/// 默认嵌入维度
inline constexpr std::size_t kDefaultEmbeddingDim = 128;
/// 内存对齐字节数（匹配 AVX2 缓存行宽度）
inline constexpr std::size_t kAlignmentBytes = 64;

// ── 前向声明 ─────────────────────────────────────────────────
template <typename T> class FeatureGraph;

/**
 * @brief 单个特征图节点
 *
 * @tparam T  标量类型（float 或 double）
 *
 * 布局经过对齐优化：
 *  - embedding 指针 64 字节对齐，适合 _mm256_load_ps 等 AVX 指令
 *  - 通过 padding 保证结构体本身也是缓存行的整数倍
 */
template <typename T>
struct alignas(kAlignmentBytes) FeatureNode {
    /// 节点唯一标识符
    uint32_t id;
    /// 标签索引（离散类别 ID）
    uint32_t label_id;
    /// 到质心的欧氏距离平方（由 compute_centroid_distances 填充）
    T        dist_sq_to_centroid;
    /// BFS 孤立度分数（由 bfs_isolation_score 填充）
    T        isolation_score;
    /// 邻接表：存储与此节点距离低于阈值的邻居索引
    std::vector<uint32_t> neighbors;
    /// 高维嵌入向量（堆上分配，64 字节对齐）
    std::vector<T, std::allocator<T>> embedding;

    /** @brief 默认构造 */
    FeatureNode() : id(0), label_id(0), dist_sq_to_centroid(0), isolation_score(0) {}

    /** @brief 带嵌入的构造 */
    FeatureNode(uint32_t node_id, uint32_t lbl, const std::vector<T>& emb)
        : id(node_id), label_id(lbl), dist_sq_to_centroid(0),
          isolation_score(0), embedding(emb) {}
};

/**
 * @brief 高维特征图管理器
 *
 * 管理一组 FeatureNode，提供：
 *  - 质心距离批量计算（OpenMP 并行）
 *  - 基于 BFS 的异常节点检测
 *  - 邻接图构建（基于距离阈值）
 *  - 与 Python 端的数据序列化接口
 */
template <typename T>
class FeatureGraph {
public:
    using value_type  = T;
    using node_type   = FeatureNode<T>;
    using node_vector = std::vector<node_type>;

    /** @brief 默认构造 */
    FeatureGraph();

    /** @brief 指定维度的构造 */
    explicit FeatureGraph(std::size_t embedding_dim);

    /** @brief 析构 */
    ~FeatureGraph();

    // ── 禁止拷贝，允许移动 ────────────────────────────────────
    FeatureGraph(const FeatureGraph&)            = delete;
    FeatureGraph& operator=(const FeatureGraph&) = delete;
    FeatureGraph(FeatureGraph&&) noexcept         = default;
    FeatureGraph& operator=(FeatureGraph&&) noexcept = default;

    // ── 节点管理 ─────────────────────────────────────────────
    /**
     * @brief 添加一个节点
     * @param id          节点 ID
     * @param label_id    标签 ID
     * @param embedding   长度必须 == embedding_dim()
     */
    void add_node(uint32_t id, uint32_t label_id, const std::vector<T>& embedding);

    /**
     * @brief 批量添加节点（避免多次 realloc）
     */
    void add_nodes_batch(const std::vector<uint32_t>& ids,
                         const std::vector<uint32_t>& labels,
                         const std::vector<std::vector<T>>& embeddings);

    /** @brief 返回当前节点数量 */
    [[nodiscard]] std::size_t size() const noexcept { return nodes_.size(); }

    /** @brief 返回嵌入维度 */
    [[nodiscard]] std::size_t embedding_dim() const noexcept { return embedding_dim_; }

    /** @brief 访问节点（只读） */
    [[nodiscard]] const node_type& node(std::size_t idx) const { return nodes_.at(idx); }

    /** @brief 访问节点（可写） */
    [[nodiscard]] node_type& node(std::size_t idx) { return nodes_.at(idx); }

    /** @brief 获取全部节点的只读引用 */
    [[nodiscard]] const node_vector& nodes() const noexcept { return nodes_; }

    // ── 核心算法 ─────────────────────────────────────────────

    /**
     * @brief 批量计算每个节点到质心的欧氏距离平方
     *
     * 并行策略：OpenMP parallel for 动态调度
     * 复杂度：O(N * D)，N = 节点数，D = 维度
     */
    void compute_centroid_distances();

    /**
     * @brief 基于距离阈值构建邻接图
     *
     * 对每个节点，将距离小于 threshold 的其他节点加入邻居列表。
     * 并行策略：OpenMP parallel for + 线程局部缓冲区
     *
     * @param threshold  欧氏距离阈值（非平方值）
     */
    void build_adjacency_graph(T threshold);

    /**
     * @brief BFS 孤立度评分
     *
     * 从质心最近的 K 个节点出发执行 BFS，记录每个节点被 BFS
     * 第一次访问时的跳数（hop count）。跳数越大 → 节点越孤立。
     * 未被访问的节点获得最大分数 max_hops + 1。
     *
     * @param k_nearest   从距质心最近的 k 个种子节点发起 BFS
     * @param max_hops    BFS 最大搜索深度
     * @return            按 isolation_score 降序排列的 (node_index, score) 对
     */
    std::vector<std::pair<uint32_t, T>> bfs_isolation_score(
        std::size_t k_nearest, std::size_t max_hops);

    /**
     * @brief 返回距质心最远的 top_n 个节点索引（已按距离降序排列）
     */
    [[nodiscard]] std::vector<uint32_t> top_outliers(std::size_t top_n) const;

    // ── 序列化 ───────────────────────────────────────────────

    /**
     * @brief 导出所有节点的 isolation_score 和 id（供 pybind11 桥接）
     * @return (ids, scores) 两个等长向量
     */
    [[nodiscard]] std::pair<std::vector<uint32_t>, std::vector<T>>
    export_isolation_results() const;

    /** @brief 清空所有节点与邻接信息 */
    void clear() noexcept;

private:
    /// 嵌入维度
    std::size_t embedding_dim_;
    /// 节点存储
    node_vector nodes_;
    /// 质心向量（长度 == embedding_dim_）
    std::vector<T> centroid_;

    /** @brief 重新计算质心 */
    void recompute_centroid();

    /** @brief 平方欧氏距离（无 OpenMP 标量版本） */
    [[nodiscard]] T dist_sq(const std::vector<T>& a, const std::vector<T>& b) const;
};

// ── 显式实例化声明 ───────────────────────────────────────────
extern template class FeatureGraph<float>;
extern template class FeatureGraph<double>;

}  // namespace fg
