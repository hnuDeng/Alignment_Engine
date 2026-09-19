/**
 * @file  graph_algorithms.h
 * @brief 无锁队列 + BFS + Dijkstra -- 高维特征流形图计算引擎
 *
 * 设计目标：
 *  1. 手写无向图数据结构，禁止调用第三方图库
 *  2. 基于 MPMC 无锁环形队列的多线程 BFS（OpenMP 并行邻居扩展）
 *  3. Dijkstra 最短路径用于检测分布漂移边界
 *  4. 使用内存池分配特征向量，避免频繁 new/delete
 *
 * 并发模型：
 *  - BFS：主线程通过无锁队列分发任务，OpenMP parallel for 并行扩展邻居
 *  - Dijkstra：OpenMP parallel for 并行松弛所有边
 *  - 无锁队列：基于 atomic sequence number 的 MPMC 环形缓冲区
 *
 * 时间/空间复杂度推导在每个方法的注释中。
 */

#pragma once

#include "memory_pool.h"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <limits>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace ga {

// -- Constants ------------------------------------------------------------
inline constexpr std::size_t kDefaultDim     = 128;
inline constexpr std::size_t kCacheLineBytes = 64;
inline constexpr double      kInfDist        = std::numeric_limits<double>::infinity();
inline constexpr uint32_t    kUnvisited      = UINT32_MAX;

// =========================================================================
// LockFreeQueue -- MPMC 无锁环形队列
//
// 基于 Dmitry Vyukov 的 bounded MPMC queue 设计：
//  - 容量必须是 2 的幂（用位运算替代取模）
//  - 每个槽位有一个 atomic sequence number
//  - push/pop 都是 wait-free 的（单次 CAS 成功即完成）
//
// 时间复杂度：
//  - push: O(1) 摊还（CAS 失败时自旋重试）
//  - pop:  O(1) 摊还（CAS 失败时自旋重试）
//
// 空间复杂度：
//  - O(capacity * (sizeof(T) + sizeof(std::atomic<size_t>)))
//  - 加上 padding 避免 false sharing
// =========================================================================

template <typename T>
class LockFreeQueue {
public:
    /**
     * @brief 构造无锁队列
     * @param min_capacity  最小容量（会被向上取整到最近的 2 的幂）
     *
     * 空间复杂度：O(capacity * cache_line_size)
     */
    explicit LockFreeQueue(std::size_t min_capacity = 1024)
        : capacity_(next_power_of_two(min_capacity)),
          mask_(capacity_ - 1),
          buffer_(new Slot[capacity_])
    {
        for (std::size_t i = 0; i < capacity_; ++i) {
            buffer_[i].sequence.store(i, std::memory_order_relaxed);
        }
        enqueue_pos_.store(0, std::memory_order_relaxed);
        dequeue_pos_.store(0, std::memory_order_relaxed);
    }

    ~LockFreeQueue() = default;

    // 禁止拷贝和移动（atomic 不可复制）
    LockFreeQueue(const LockFreeQueue&)            = delete;
    LockFreeQueue& operator=(const LockFreeQueue&) = delete;
    LockFreeQueue(LockFreeQueue&&)                 = delete;
    LockFreeQueue& operator=(LockFreeQueue&&)      = delete;

    /**
     * @brief 向队列尾部插入一个元素
     * @param value  要插入的值
     * @return true 如果成功入队，false 如果队列已满
     *
     * 时间复杂度：O(1) 摊还
     * 并发安全：多线程可同时调用
     */
    bool push(const T& value)
    {
        Slot* slot;
        std::size_t pos = enqueue_pos_.load(std::memory_order_relaxed);

        for (;;) {
            slot = &buffer_[pos & mask_];
            std::size_t seq = slot->sequence.load(std::memory_order_acquire);
            intptr_t diff = static_cast<intptr_t>(seq) - static_cast<intptr_t>(pos);

            if (diff == 0) {
                // Slot is free -- try to claim it
                if (enqueue_pos_.compare_exchange_weak(
                        pos, pos + 1, std::memory_order_relaxed)) {
                    break;
                }
                // CAS failed, pos updated by compare_exchange_weak, retry
            } else if (diff < 0) {
                // Queue is full
                return false;
            } else {
                // Another thread claimed this slot, refresh pos
                pos = enqueue_pos_.load(std::memory_order_relaxed);
            }
        }

        slot->data = value;
        slot->sequence.store(pos + 1, std::memory_order_release);
        return true;
    }

    /**
     * @brief 向队列尾部插入一个元素（移动语义）
     */
    bool push(T&& value)
    {
        Slot* slot;
        std::size_t pos = enqueue_pos_.load(std::memory_order_relaxed);

        for (;;) {
            slot = &buffer_[pos & mask_];
            std::size_t seq = slot->sequence.load(std::memory_order_acquire);
            intptr_t diff = static_cast<intptr_t>(seq) - static_cast<intptr_t>(pos);

            if (diff == 0) {
                if (enqueue_pos_.compare_exchange_weak(
                        pos, pos + 1, std::memory_order_relaxed)) {
                    break;
                }
            } else if (diff < 0) {
                return false;
            } else {
                pos = enqueue_pos_.load(std::memory_order_relaxed);
            }
        }

        slot->data = std::move(value);
        slot->sequence.store(pos + 1, std::memory_order_release);
        return true;
    }

    /**
     * @brief 从队列头部取出一个元素
     * @param result  输出参数，接收取出的值
     * @return true 如果成功出队，false 如果队列为空
     *
     * 时间复杂度：O(1) 摊还
     * 并发安全：多线程可同时调用
     */
    bool pop(T& result)
    {
        Slot* slot;
        std::size_t pos = dequeue_pos_.load(std::memory_order_relaxed);

        for (;;) {
            slot = &buffer_[pos & mask_];
            std::size_t seq = slot->sequence.load(std::memory_order_acquire);
            intptr_t diff = static_cast<intptr_t>(seq) - static_cast<intptr_t>(pos + 1);

            if (diff == 0) {
                // Slot has data -- try to claim it
                if (dequeue_pos_.compare_exchange_weak(
                        pos, pos + 1, std::memory_order_relaxed)) {
                    break;
                }
            } else if (diff < 0) {
                // Queue is empty
                return false;
            } else {
                // Another thread already dequeued this element
                pos = dequeue_pos_.load(std::memory_order_relaxed);
            }
        }

        result = std::move(slot->data);
        slot->sequence.store(pos + capacity_, std::memory_order_release);
        return true;
    }

    /**
     * @brief 检查队列是否为空
     * 注意：在并发环境下，返回值可能瞬间过期
     */
    [[nodiscard]] bool empty() const noexcept
    {
        return enqueue_pos_.load(std::memory_order_relaxed) ==
               dequeue_pos_.load(std::memory_order_relaxed);
    }

private:
    /// Cache-line padded slot to avoid false sharing between enqueue/dequeue positions
    struct alignas(kCacheLineBytes) Slot {
        std::atomic<std::size_t> sequence;
        T                        data;
    };

    const std::size_t capacity_;  ///< Queue capacity (must be power of 2)
    const std::size_t mask_;      ///< capacity_ - 1, for bitwise modulo
    std::unique_ptr<Slot[]> buffer_;

    alignas(kCacheLineBytes) std::atomic<std::size_t> enqueue_pos_;
    alignas(kCacheLineBytes) std::atomic<std::size_t> dequeue_pos_;

    /**
     * @brief Round n up to the nearest power of 2
     *
     * Bit-twiddling: set all bits below the highest bit, then +1
     * e.g. 5 -> 0b101 -> 0b111 -> 0b1000 = 8
     */
    static std::size_t next_power_of_two(std::size_t n) noexcept
    {
        if (n == 0) return 1;
        --n;
        n |= n >> 1;
        n |= n >> 2;
        n |= n >> 4;
        n |= n >> 8;
        n |= n >> 16;
        if constexpr (sizeof(std::size_t) > 4) {
            n |= n >> 32;
        }
        return n + 1;
    }
};

// =========================================================================
// GraphEngine -- 特征空间图计算引擎
//
// 使用 PoolAllocator 管理特征向量内存，
// 提供 BFS 和 Dijkstra 算法用于检测孤立点和漂移边界。
// =========================================================================

/**
 * @brief BFS 遍历结果
 *
 * 时间复杂度：O(V + E)，其中 V = 节点数，E = 边数
 * 空间复杂度：O(V)
 */
struct BFSResult {
    /// 从源节点到每个节点的跳数（kUnvisited 表示不可达）
    std::vector<uint32_t> distance;
    /// BFS 访问顺序
    std::vector<uint32_t> visit_order;
    /// 孤立节点列表（距离 > max_depth 或不可达）
    std::vector<uint32_t> isolated_nodes;
    /// 最大实际访问深度
    uint32_t max_depth_reached;
};

/**
 * @brief Dijkstra 最短路径结果
 *
 * 时间复杂度：O((V + E) log V)（二叉堆优先队列）
 * 空间复杂度：O(V)
 */
struct DijkstraResult {
    /// 从源节点到每个节点的最短距离（kInfDist 表示不可达）
    std::vector<double> distance;
    /// 最短路径树：predecessor[v] = v 的前驱节点
    std::vector<uint32_t> predecessor;
    /// 按距离排序的可达节点列表
    std::vector<uint32_t> reachable_nodes;
};

// =========================================================================
// 自定义异常层级（>= 3 个 per engineering contract）
// =========================================================================

class GraphEngineException : public std::runtime_error {
public:
    explicit GraphEngineException(const std::string& msg)
        : std::runtime_error("[GraphEngine] " + msg) {}
};

class NodeNotFoundException : public GraphEngineException {
public:
    explicit NodeNotFoundException(uint32_t node_id)
        : GraphEngineException(
              "Node not found: id=" + std::to_string(node_id)) {}
};

class DuplicateNodeException : public GraphEngineException {
public:
    explicit DuplicateNodeException(uint32_t node_id)
        : GraphEngineException(
              "Duplicate node: id=" + std::to_string(node_id) +
              " already exists") {}
};

class EmbeddingDimensionException : public GraphEngineException {
public:
    EmbeddingDimensionException(std::size_t expected, std::size_t actual)
        : GraphEngineException(
              "Embedding dimension mismatch: expected=" +
              std::to_string(expected) + ", got=" + std::to_string(actual)) {}
};

// =========================================================================
// GraphEngine class
// =========================================================================

/**
 * @brief 特征空间图计算引擎
 *
 * 核心职责：
 *  1. 管理节点（特征向量存储在内存池中）
 *  2. 维护无向加权邻接表
 *  3. 执行 BFS 孤立点检测和 Dijkstra 漂移边界分析
 *
 * 内存管理：
 *  - 特征向量通过 PoolAllocator 分配，64 字节 SIMD 对齐
 *  - 邻接表使用 std::vector<Neighbor> 存储
 *  - 析构时通过内存池统一释放所有向量
 *
 * 线程安全：
 *  - 非线程安全，单线程使用
 *  - BFS/Dijkstra 内部使用 OpenMP 并行化
 */
class GraphEngine {
public:
    /**
     * @brief 构造图引擎
     * @param embedding_dim  特征向量维度（默认 128）
     * @param initial_pool_capacity  内存池初始容量
     *
     * 时间复杂度：O(initial_pool_capacity)（预分配内存池）
     * 空间复杂度：O(initial_pool_capacity * block_size)
     */
    explicit GraphEngine(
        std::size_t embedding_dim          = kDefaultDim,
        std::size_t initial_pool_capacity  = 4096
    );

    ~GraphEngine();

    // 禁止拷贝，允许移动
    GraphEngine(const GraphEngine&)            = delete;
    GraphEngine& operator=(const GraphEngine&) = delete;
    GraphEngine(GraphEngine&&) noexcept         = default;
    GraphEngine& operator=(GraphEngine&&) noexcept = default;

    // -- Node management --------------------------------------------------

    /**
     * @brief 添加一个节点
     * @param id         节点唯一标识符
     * @param label_id   类别标签
     * @param embedding  特征向量（长度必须 == embedding_dim）
     *
     * 时间复杂度：O(D)（向量拷贝 + 内存池分配）
     * 空间复杂度：O(D)（特征向量存储）
     *
     * @throws EmbeddingDimensionException 如果 embedding.size() != embedding_dim
     * @throws DuplicateNodeException       如果 id 已存在
     */
    void add_node(uint32_t id, uint32_t label_id,
                  const std::vector<float>& embedding);

    /**
     * @brief 添加一条无向边
     * @param src_id  源节点 ID
     * @param dst_id  目标节点 ID
     * @param weight  边权重（欧氏距离）
     *
     * 时间复杂度：O(1)
     *
     * @throws NodeNotFoundException 如果 src_id 或 dst_id 不存在
     */
    void add_edge(uint32_t src_id, uint32_t dst_id, double weight);

    /**
     * @brief 获取节点的特征向量
     *
     * 时间复杂度：O(D)
     * 空间复杂度：O(D)（返回拷贝）
     *
     * @throws NodeNotFoundException 如果 id 不存在
     */
    [[nodiscard]] std::vector<float> get_embedding(uint32_t id) const;

    [[nodiscard]] std::size_t size() const noexcept { return node_count_; }
    [[nodiscard]] std::size_t embedding_dim() const noexcept { return dim_; }
    [[nodiscard]] bool has_node(uint32_t id) const noexcept;

    /**
     * @brief 获取内存池统计
     */
    [[nodiscard]] mp::PoolStats pool_stats() const noexcept;

    /**
     * @brief 清空图（释放所有内存池块）
     *
     * 时间复杂度：O(N)（释放所有块）
     */
    void clear() noexcept;

    // -- Algorithm 1: BFS isolation detection -----------------------------

    /**
     * @brief 从指定源节点执行 BFS，检测孤立节点
     *
     * 并行策略：
     *  - 每层的邻居扩展通过 OpenMP parallel for 并行
     *  - 使用无锁队列在主线程和并行区域之间传递节点
     *
     * 时间复杂度：O(V + E)
     *  - V 次节点访问，每次 O(1)
     *  - E 次边检查，每次 O(1)
     * 空间复杂度：O(V + E)
     *  - distance 数组：O(V)
     *  - 无锁队列：O(min(V, queue_capacity))
     *  - visited 标记：O(V)
     *
     * @param source_id  源节点 ID
     * @param max_depth  最大搜索深度（0 = 无限制）
     * @return BFSResult
     *
     * @throws NodeNotFoundException 如果 source_id 不存在
     */
    BFSResult bfs(uint32_t source_id, uint32_t max_depth = 0) const;

    // -- Algorithm 2: Dijkstra shortest path ------------------------------

    /**
     * @brief 从指定源节点执行 Dijkstra 最短路径算法
     *
     * 并行策略：
     *  - 松弛阶段通过 OpenMP parallel for 并行检查所有边
     *  - 使用 #pragma omp critical 保护距离更新
     *
     * 时间复杂度：O((V + E) * log V)（二叉堆版本）
     *  - V 次 extract-min，每次 O(log V)
     *  - E 次 decrease-key，每次 O(log V)
     * 空间复杂度：O(V + E)
     *  - 距离数组：O(V)
     *  - 前驱数组：O(V)
     *  - 优先队列：O(V)
     *
     * @param source_id    源节点 ID
     * @param max_edges    最大松弛边数（0 = 全部）
     * @return DijkstraResult
     *
     * @throws NodeNotFoundException 如果 source_id 不存在
     */
    DijkstraResult dijkstra(uint32_t source_id,
                            std::size_t max_edges = 0) const;

    // -- Query ------------------------------------------------------------

    /**
     * @brief 获取所有节点 ID
     */
    [[nodiscard]] std::vector<uint32_t> node_ids() const;

    /**
     * @brief 获取指定节点的邻居数量
     *
     * @throws NodeNotFoundException 如果 id 不存在
     */
    [[nodiscard]] std::size_t neighbor_count(uint32_t id) const;

private:
    /// 邻居信息
    struct Neighbor {
        uint32_t node_id;    ///< 邻居节点 ID
        double   weight;     ///< 边权重（欧氏距离）
    };

    /// 节点元数据
    struct NodeInfo {
        uint32_t label_id;       ///< 类别标签
        void*     block_ptr;     ///< 内存池块指针（用于读回特征向量）
        std::vector<Neighbor> adjacency;  ///< 邻接表
    };

    /// 嵌入维度
    std::size_t dim_;
    /// 节点计数
    std::size_t node_count_;
    /// SIMD 对齐内存池（存储特征向量）
    mp::FeatureVectorPool pool_;
    /// 节点 ID -> NodeInfo pairs (linear scan for small graphs, upgrade to hashmap for >10k nodes)
    std::vector<std::pair<uint32_t, NodeInfo>> nodes_;

    /**
     * @brief 查找节点在 nodes_ 中的位置
     * @return nodes_ 中的索引
     * @throws NodeNotFoundException 如果不存在
     */
    std::size_t find_node_index(uint32_t id) const;

    /**
     * @brief 获取节点 ID 对应的内部索引（不抛异常）
     * @return 索引，或 SIZE_MAX 表示未找到
     */
    [[nodiscard]] std::size_t find_node_index_safe(uint32_t id) const noexcept;
};

}  // namespace ga
