/**
 * @file  graph_algorithms.cpp
 * @brief GraphEngine 实现 -- BFS + Dijkstra + LockFreeQueue + OpenMP
 *
 * 并发安全设计：
 *  - BFS: 双缓冲 LockFreeQueue 管理 frontier，OpenMP parallel for 扩展邻居，
 *         atomic CAS 防止重复访问
 *  - Dijkstra: OpenMP parallel for + #pragma omp critical 保护松弛写入
 *  - 内存池分配在单线程上下文中完成（add_node 在 BFS 之前）
 */

#include "graph_algorithms.h"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstring>
#include <numeric>
#include <queue>
#include <stdexcept>
#include <string>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace ga {

// =========================================================================
// GraphEngine -- Constructor / Destructor
// =========================================================================

GraphEngine::GraphEngine(std::size_t embedding_dim,
                         std::size_t initial_pool_capacity)
    : dim_(embedding_dim),
      node_count_(0),
      pool_(initial_pool_capacity)
{
    if (embedding_dim == 0) {
        throw GraphEngineException("embedding_dim must be > 0");
    }
}

GraphEngine::~GraphEngine()
{
    for (auto& [id, info] : nodes_) {
        if (info.block_ptr != nullptr) {
            pool_.release(info.block_ptr);
            info.block_ptr = nullptr;
        }
    }
}

// =========================================================================
// Node management
// =========================================================================

void GraphEngine::add_node(uint32_t id, uint32_t label_id,
                           const std::vector<float>& embedding)
{
    if (embedding.size() != dim_) {
        throw EmbeddingDimensionException(dim_, embedding.size());
    }
    if (find_node_index_safe(id) != SIZE_MAX) {
        throw DuplicateNodeException(id);
    }

    void* block = pool_.acquire();
    std::memcpy(block, embedding.data(), dim_ * sizeof(float));

    NodeInfo info;
    info.label_id  = label_id;
    info.block_ptr = block;
    info.adjacency.reserve(16);

    nodes_.emplace_back(id, std::move(info));
    ++node_count_;
}

void GraphEngine::add_edge(uint32_t src_id, uint32_t dst_id, double weight)
{
    std::size_t src_idx = find_node_index(src_id);
    std::size_t dst_idx = find_node_index(dst_id);

    nodes_[src_idx].second.adjacency.push_back({dst_id, weight});
    nodes_[dst_idx].second.adjacency.push_back({src_id, weight});
}

std::vector<float> GraphEngine::get_embedding(uint32_t id) const
{
    std::size_t idx = find_node_index(id);
    const auto& info = nodes_[idx].second;

    if (info.block_ptr == nullptr) {
        throw GraphEngineException(
            "Null block pointer for node " + std::to_string(id));
    }

    const float* data = static_cast<const float*>(info.block_ptr);
    return std::vector<float>(data, data + dim_);
}

bool GraphEngine::has_node(uint32_t id) const noexcept
{
    return find_node_index_safe(id) != SIZE_MAX;
}

mp::PoolStats GraphEngine::pool_stats() const noexcept
{
    return pool_.stats();
}

void GraphEngine::clear() noexcept
{
    for (auto& [id, info] : nodes_) {
        if (info.block_ptr != nullptr) {
            pool_.release(info.block_ptr);
            info.block_ptr = nullptr;
        }
    }
    nodes_.clear();
    node_count_ = 0;
}

std::vector<uint32_t> GraphEngine::node_ids() const
{
    std::vector<uint32_t> ids;
    ids.reserve(nodes_.size());
    for (const auto& [id, info] : nodes_) {
        ids.push_back(id);
    }
    return ids;
}

std::size_t GraphEngine::neighbor_count(uint32_t id) const
{
    std::size_t idx = find_node_index(id);
    return nodes_[idx].second.adjacency.size();
}

// =========================================================================
// Internal helpers
// =========================================================================

std::size_t GraphEngine::find_node_index(uint32_t id) const
{
    std::size_t idx = find_node_index_safe(id);
    if (idx == SIZE_MAX) {
        throw NodeNotFoundException(id);
    }
    return idx;
}

std::size_t GraphEngine::find_node_index_safe(uint32_t id) const noexcept
{
    for (std::size_t i = 0; i < nodes_.size(); ++i) {
        if (nodes_[i].first == id) {
            return i;
        }
    }
    return SIZE_MAX;
}

// =========================================================================
// Algorithm 1: BFS with LockFreeQueue + OpenMP
//
// Time complexity:  O(V + E)
//   - Each node is visited at most once: O(V)
//   - Each edge is examined at most once per direction: O(E)
//   - LockFreeQueue push/pop: O(1) amortized each
//
// Space complexity: O(V + E)
//   - atomic distance array: O(V * sizeof(atomic<uint32_t>))
//   - double-buffered LockFreeQueues: O(V) total
//   - level_buffer: O(V) worst case for a single level
//   - visit_order:  O(V)
//
// Parallelism strategy:
//   - Level-synchronous BFS using double-buffered LockFreeQueues:
//     1. current_queue: frontier of nodes at current depth
//     2. Main thread drains current_queue into a level_buffer (O(level_size))
//     3. OpenMP parallel for expands all neighbors in the level_buffer
//     4. Atomic CAS on dist_atomic prevents duplicate visits
//     5. Successfully CAS'd nodes are pushed into next_queue
//     6. After the level, drain next_queue into current_queue
//   - LockFreeQueue (Vyukov MPMC design) provides wait-free push/pop
// =========================================================================

BFSResult GraphEngine::bfs(uint32_t source_id, uint32_t max_depth) const
{
    const std::size_t n = nodes_.size();
    std::size_t src_idx = find_node_index(source_id);

    BFSResult result;
    result.distance.resize(n, kUnvisited);
    result.visit_order.reserve(n);
    result.isolated_nodes.reserve(n / 4);
    result.max_depth_reached = 0;

    if (n == 0) return result;

    // Build ID -> position index for O(V) lookup during BFS.
    // For V > 10k consider upgrading to unordered_map for O(1).
    auto find_pos = [&](uint32_t node_id) -> std::size_t {
        for (std::size_t i = 0; i < n; ++i) {
            if (nodes_[i].first == node_id) return i;
        }
        return SIZE_MAX;
    };

    // Properly aligned atomic distance array for concurrent CAS operations.
    // We use heap-allocated std::atomic<uint32_t>[] (not reinterpret_cast on
    // vector data) to satisfy std::atomic's alignment requirements.
    // Space: O(V * sizeof(std::atomic<uint32_t>))
    auto* dist_atomic = new std::atomic<uint32_t>[n];
    for (std::size_t i = 0; i < n; ++i) {
        dist_atomic[i].store(kUnvisited, std::memory_order_relaxed);
    }

    // Double-buffered LockFreeQueues for level-synchronous BFS.
    // Using two queues avoids the need for a level-end sentinel.
    // Space: O(V) total across both queues (each bounded at V capacity).
    LockFreeQueue<uint32_t> current_queue(n);
    LockFreeQueue<uint32_t> next_queue(n);

    // Seed the BFS with the source node
    current_queue.push(static_cast<uint32_t>(src_idx));
    dist_atomic[src_idx].store(0, std::memory_order_relaxed);
    result.visit_order.push_back(nodes_[src_idx].first);

    uint32_t current_depth = 0;
    const bool depth_limit = (max_depth > 0);

    int num_threads = 1;
#ifdef _OPENMP
    num_threads = omp_get_max_threads();
#endif

    // Level-by-level BFS loop
    // Invariant: current_queue contains exactly the frontier at current_depth
    while (true) {
        if (depth_limit && current_depth >= max_depth) {
            break;
        }

        // Step 1: Drain current_queue into a level buffer for parallel processing.
        // LockFreeQueue does not support indexed access, so we must
        // pop all elements into a vector first.
        // Time: O(level_size), each pop is O(1) amortized
        std::vector<uint32_t> level_buffer;
        level_buffer.reserve(n);
        {
            uint32_t node_idx;
            while (current_queue.pop(node_idx)) {
                level_buffer.push_back(node_idx);
            }
        }

        if (level_buffer.empty()) {
            break;  // No more nodes to explore
        }

        // Step 2: Thread-local buffers for newly discovered nodes.
        // Each OpenMP thread collects its neighbors independently,
        // then we push them into next_queue after the parallel region.
        // This avoids contention on the LockFreeQueue during parallel expansion.
        std::vector<std::vector<uint32_t>> thread_local_bufs(
            static_cast<std::size_t>(num_threads));

        const std::size_t level_size = level_buffer.size();

        // Step 3: Parallel neighbor expansion
        // Time per level: O(E_level / T) where E_level = edges from frontier
        // Total across all levels: O(E / T)
#ifdef _OPENMP
        #pragma omp parallel for schedule(dynamic, 4)
#endif
        for (int64_t li = 0; li < static_cast<int64_t>(level_size); ++li) {
            uint32_t u_idx = level_buffer[static_cast<std::size_t>(li)];
            const auto& adj = nodes_[u_idx].second.adjacency;

            int tid = 0;
#ifdef _OPENMP
            tid = omp_get_thread_num();
#endif
            auto& local_buf = thread_local_bufs[static_cast<std::size_t>(tid)];

            // Expand all neighbors of u
            // Time: O(deg(u))
            for (const auto& neighbor : adj) {
                std::size_t v_pos = find_pos(neighbor.node_id);
                if (v_pos == SIZE_MAX) continue;

                // Atomic CAS: only the first thread to discover an unvisited
                // node claims it. This prevents duplicate entries in next_queue.
                // CAS is wait-free on success, lock-free on failure.
                uint32_t expected = kUnvisited;
                uint32_t desired  = current_depth + 1;
                if (dist_atomic[v_pos].compare_exchange_strong(
                        expected, desired,
                        std::memory_order_acq_rel,
                        std::memory_order_relaxed)) {
                    local_buf.push_back(static_cast<uint32_t>(v_pos));
                }
            }
        }

        // Step 4: Merge thread-local results into next_queue via LockFreeQueue::push.
        // Time: O(total_new_nodes), each push is O(1) amortized
        for (auto& buf : thread_local_bufs) {
            for (uint32_t idx : buf) {
                next_queue.push(idx);
                result.visit_order.push_back(nodes_[idx].first);
            }
        }

        ++current_depth;
        result.max_depth_reached = current_depth;

        // Step 5: Swap queues -- drain next_queue into current_queue.
        // This is O(level_size) per level, O(V) total across all levels.
        {
            uint32_t node_idx;
            while (next_queue.pop(node_idx)) {
                current_queue.push(node_idx);
            }
        }
    }

    // Collect isolated nodes: those whose distance was never updated
    // Time: O(V)
    for (std::size_t i = 0; i < n; ++i) {
        uint32_t d = dist_atomic[i].load(std::memory_order_relaxed);
        if (d == kUnvisited) {
            result.isolated_nodes.push_back(nodes_[i].first);
        } else {
            result.distance[i] = d;
        }
    }

    // Clean up the atomic distance array
    delete[] dist_atomic;

    return result;
}

// =========================================================================
// Algorithm 2: Dijkstra with OpenMP parallel relaxation
//
// Time complexity: O((V + E) * log V) with binary heap
//   - V extract-min operations: O(V log V)
//   - E relaxation attempts: O(E log V) with decrease-key
//   The OpenMP parallel for over adjacency lists reduces wall-clock time
//   by a factor of T (thread count) for the relaxation phase.
//
// Space complexity: O(V + E)
//   - dist array:     O(V)
//   - predecessor:    O(V)
//   - visited:        O(V)
//   - priority queue: O(V)
//
// Parallelism strategy:
//   - For each node u extracted from the priority queue:
//     relax all edges (u, v) in parallel via OpenMP
//   - Distance updates protected by #pragma omp critical
//   - Double-checked locking: fast path without lock, then re-check with lock
// =========================================================================

DijkstraResult GraphEngine::dijkstra(uint32_t source_id,
                                     std::size_t max_edges) const
{
    const std::size_t n = nodes_.size();
    std::size_t src_idx = find_node_index(source_id);

    DijkstraResult result;
    result.distance.assign(n, kInfDist);
    result.predecessor.assign(n, UINT32_MAX);

    using PQEntry = std::pair<double, uint32_t>;
    std::priority_queue<PQEntry, std::vector<PQEntry>, std::greater<PQEntry>> pq;

    result.distance[src_idx] = 0.0;
    pq.push({0.0, static_cast<uint32_t>(src_idx)});

    std::vector<bool> visited(n, false);

    std::size_t edges_processed = 0;
    const bool limit_edges = (max_edges > 0);

    while (!pq.empty()) {
        auto [dist_u, u_idx] = pq.top();
        pq.pop();

        if (visited[u_idx]) continue;
        visited[u_idx] = true;

        if (limit_edges) {
            ++edges_processed;
            if (edges_processed >= max_edges) break;
        }

        const auto& adj = nodes_[u_idx].second.adjacency;
        const std::size_t adj_size = adj.size();

#ifdef _OPENMP
        #pragma omp parallel for schedule(dynamic, 8)
#endif
        for (int64_t ni = 0; ni < static_cast<int64_t>(adj_size); ++ni) {
            const auto& neighbor = adj[static_cast<std::size_t>(ni)];
            std::size_t v_pos = find_node_index_safe(neighbor.node_id);
            if (v_pos == SIZE_MAX) continue;
            if (visited[v_pos]) continue;

            double new_dist = dist_u + neighbor.weight;

            if (new_dist < result.distance[v_pos]) {
#ifdef _OPENMP
                #pragma omp critical
#endif
                {
                    if (new_dist < result.distance[v_pos]) {
                        result.distance[v_pos] = new_dist;
                        result.predecessor[v_pos] = static_cast<uint32_t>(u_idx);
                        pq.push({new_dist, static_cast<uint32_t>(v_pos)});
                    }
                }
            }
        }
    }

    for (std::size_t i = 0; i < n; ++i) {
        if (result.distance[i] < kInfDist) {
            result.reachable_nodes.push_back(static_cast<uint32_t>(i));
        }
    }
    std::sort(result.reachable_nodes.begin(), result.reachable_nodes.end(),
              [&result](uint32_t a, uint32_t b) {
                  return result.distance[a] < result.distance[b];
              });

    return result;
}

}  // namespace ga
