/**
 * @file  test_graph_algorithms.cpp
 * @brief GraphEngine C++ 单元测试
 *
 * 编译：cmake --build . --target test_graph_algorithms
 * 运行：./test_graph_algorithms
 */

#include "graph_algorithms.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <vector>

#define TEST(name) \
    static void test_##name(); \
    struct Register_##name { \
        Register_##name() { std::cout << "  [RUN] " #name << std::endl; test_##name(); std::cout << "  [PASS] " #name << std::endl; } \
    } reg_##name; \
    static void test_##name()

// Helper: create a 128-dim float vector with a given pattern
static std::vector<float> make_embedding(float base) {
    return std::vector<float>(128, base);
}

// =========================================================================
// Test 1: Basic node management
// =========================================================================
TEST(add_node_and_query) {
    ga::GraphEngine engine(128, 64);

    engine.add_node(0, 0, make_embedding(1.0f));
    engine.add_node(1, 1, make_embedding(2.0f));
    engine.add_node(2, 0, make_embedding(3.0f));

    assert(engine.size() == 3);
    assert(engine.has_node(0));
    assert(engine.has_node(1));
    assert(engine.has_node(2));
    assert(!engine.has_node(99));

    auto emb = engine.get_embedding(1);
    assert(emb.size() == 128);
    assert(emb[0] == 2.0f);
    assert(emb[127] == 2.0f);
}

// =========================================================================
// Test 2: Edge management
// =========================================================================
TEST(add_edge_and_neighbors) {
    ga::GraphEngine engine(128, 64);

    engine.add_node(0, 0, make_embedding(0.0f));
    engine.add_node(1, 1, make_embedding(1.0f));
    engine.add_node(2, 0, make_embedding(2.0f));

    engine.add_edge(0, 1, 1.0);
    engine.add_edge(0, 2, 2.0);

    assert(engine.neighbor_count(0) == 2);
    assert(engine.neighbor_count(1) == 1);
    assert(engine.neighbor_count(2) == 1);
}

// =========================================================================
// Test 3: BFS basic traversal
// =========================================================================
TEST(bfs_basic) {
    ga::GraphEngine engine(128, 64);

    // Build a simple chain: 0 -- 1 -- 2 -- 3
    for (uint32_t i = 0; i < 4; ++i) {
        engine.add_node(i, 0, make_embedding(static_cast<float>(i)));
    }
    engine.add_edge(0, 1, 1.0);
    engine.add_edge(1, 2, 1.0);
    engine.add_edge(2, 3, 1.0);

    auto result = engine.bfs(0, 0);

    assert(result.visit_order.size() == 4);
    assert(result.distance[0] == 0);
    assert(result.distance[1] == 1);
    assert(result.distance[2] == 2);
    assert(result.distance[3] == 3);
    assert(result.isolated_nodes.empty());
}

// =========================================================================
// Test 4: BFS with depth limit
// =========================================================================
TEST(bfs_depth_limit) {
    ga::GraphEngine engine(128, 64);

    // Chain: 0 -- 1 -- 2 -- 3 -- 4
    for (uint32_t i = 0; i < 5; ++i) {
        engine.add_node(i, 0, make_embedding(static_cast<float>(i)));
    }
    engine.add_edge(0, 1, 1.0);
    engine.add_edge(1, 2, 1.0);
    engine.add_edge(2, 3, 1.0);
    engine.add_edge(3, 4, 1.0);

    auto result = engine.bfs(0, 2);

    // Only nodes within distance 2 should be visited
    assert(result.distance[0] == 0);
    assert(result.distance[1] == 1);
    assert(result.distance[2] == 2);
    assert(result.distance[3] == ga::kUnvisited);
    assert(result.distance[4] == ga::kUnvisited);
    assert(!result.isolated_nodes.empty());
}

// =========================================================================
// Test 5: BFS isolated nodes detection
// =========================================================================
TEST(bfs_isolated_nodes) {
    ga::GraphEngine engine(128, 64);

    // Component 1: 0 -- 1
    // Component 2: 2 -- 3 (disconnected)
    engine.add_node(0, 0, make_embedding(0.0f));
    engine.add_node(1, 1, make_embedding(1.0f));
    engine.add_node(2, 0, make_embedding(2.0f));
    engine.add_node(3, 1, make_embedding(3.0f));

    engine.add_edge(0, 1, 1.0);
    engine.add_edge(2, 3, 1.0);

    auto result = engine.bfs(0, 0);

    // Nodes 2 and 3 should be isolated from source 0
    assert(result.visit_order.size() == 2);
    assert(result.isolated_nodes.size() == 2);
}

// =========================================================================
// Test 6: Dijkstra basic shortest path
// =========================================================================
TEST(dijkstra_basic) {
    ga::GraphEngine engine(128, 64);

    // Graph: 0 --1.0-- 1 --2.0-- 2
    //        0 --4.0-- 2
    engine.add_node(0, 0, make_embedding(0.0f));
    engine.add_node(1, 1, make_embedding(1.0f));
    engine.add_node(2, 0, make_embedding(2.0f));

    engine.add_edge(0, 1, 1.0);
    engine.add_edge(1, 2, 2.0);
    engine.add_edge(0, 2, 4.0);

    auto result = engine.dijkstra(0, 0);

    assert(std::abs(result.distance[0] - 0.0) < 1e-9);
    assert(std::abs(result.distance[1] - 1.0) < 1e-9);
    assert(std::abs(result.distance[2] - 3.0) < 1e-9);  // 0->1->2 = 3, not 0->2 = 4
    assert(result.predecessor[1] == 0);
    assert(result.predecessor[2] == 1);
}

// =========================================================================
// Test 7: Dijkstra with max_edges limit
// =========================================================================
TEST(dijkstra_max_edges) {
    ga::GraphEngine engine(128, 64);

    engine.add_node(0, 0, make_embedding(0.0f));
    engine.add_node(1, 1, make_embedding(1.0f));
    engine.add_node(2, 0, make_embedding(2.0f));

    engine.add_edge(0, 1, 1.0);
    engine.add_edge(1, 2, 1.0);

    // Limit to 1 edge -- should only visit source + immediate neighbors
    auto result = engine.dijkstra(0, 1);

    assert(std::abs(result.distance[0] - 0.0) < 1e-9);
    assert(std::abs(result.distance[1] - 1.0) < 1e-9);
    // Node 2 might not be reached if max_edges is too restrictive
}

// =========================================================================
// Test 8: Dijkstra disconnected graph
// =========================================================================
TEST(dijkstra_disconnected) {
    ga::GraphEngine engine(128, 64);

    engine.add_node(0, 0, make_embedding(0.0f));
    engine.add_node(1, 1, make_embedding(1.0f));
    engine.add_node(2, 0, make_embedding(2.0f));  // disconnected

    engine.add_edge(0, 1, 1.0);

    auto result = engine.dijkstra(0, 0);

    assert(std::abs(result.distance[0] - 0.0) < 1e-9);
    assert(std::abs(result.distance[1] - 1.0) < 1e-9);
    assert(result.distance[2] == ga::kInfDist);  // unreachable
}

// =========================================================================
// Test 9: Exception handling -- duplicate node
// =========================================================================
TEST(duplicate_node_throws) {
    ga::GraphEngine engine(128, 64);
    engine.add_node(0, 0, make_embedding(0.0f));

    bool caught = false;
    try {
        engine.add_node(0, 1, make_embedding(1.0f));
    } catch (const ga::DuplicateNodeException& e) {
        caught = true;
    }
    assert(caught);
}

// =========================================================================
// Test 10: Exception handling -- node not found
// =========================================================================
TEST(node_not_found_throws) {
    ga::GraphEngine engine(128, 64);

    bool caught = false;
    try {
        engine.get_embedding(99);
    } catch (const ga::NodeNotFoundException& e) {
        caught = true;
    }
    assert(caught);
}

// =========================================================================
// Test 11: Exception handling -- embedding dimension mismatch
// =========================================================================
TEST(embedding_dim_mismatch_throws) {
    ga::GraphEngine engine(128, 64);

    bool caught = false;
    try {
        engine.add_node(0, 0, std::vector<float>(64, 1.0f));  // wrong dim
    } catch (const ga::EmbeddingDimensionException& e) {
        caught = true;
    }
    assert(caught);
}

// =========================================================================
// Test 12: Pool stats after operations
// =========================================================================
TEST(pool_stats_after_ops) {
    ga::GraphEngine engine(128, 64);

    for (uint32_t i = 0; i < 10; ++i) {
        engine.add_node(i, 0, make_embedding(static_cast<float>(i)));
    }

    auto ps = engine.pool_stats();
    assert(ps.used_blocks == 10);
    assert(ps.total_blocks >= 10);

    engine.clear();
    ps = engine.pool_stats();
    assert(ps.used_blocks == 0);
}

// =========================================================================
// Test 13: Single node BFS
// =========================================================================
TEST(bfs_single_node) {
    ga::GraphEngine engine(128, 64);
    engine.add_node(0, 0, make_embedding(0.0f));

    auto result = engine.bfs(0, 0);

    assert(result.visit_order.size() == 1);
    assert(result.distance[0] == 0);
    assert(result.isolated_nodes.empty());
}

// =========================================================================
// Test 14: Node IDs and clear
// =========================================================================
TEST(node_ids_and_clear) {
    ga::GraphEngine engine(128, 64);

    engine.add_node(10, 0, make_embedding(0.0f));
    engine.add_node(20, 1, make_embedding(1.0f));
    engine.add_node(30, 0, make_embedding(2.0f));

    auto ids = engine.node_ids();
    assert(ids.size() == 3);

    engine.clear();
    assert(engine.size() == 0);
    assert(engine.node_ids().empty());
}

// =========================================================================
// Test 15: LockFreeQueue basic operations
// =========================================================================
TEST(lockfree_queue_basic) {
    ga::LockFreeQueue<int> q(8);

    assert(q.empty());

    assert(q.push(10));
    assert(q.push(20));
    assert(q.push(30));

    int val;
    assert(q.pop(val));
    assert(val == 10);
    assert(q.pop(val));
    assert(val == 20);
    assert(q.pop(val));
    assert(val == 30);
    assert(!q.pop(val));
    assert(q.empty());
}

// =========================================================================
// Test 16: LockFreeQueue capacity enforcement
// =========================================================================
TEST(lockfree_queue_capacity) {
    // Min capacity 4 -> rounds up to 4 (already power of 2)
    ga::LockFreeQueue<int> q(4);

    assert(q.push(1));
    assert(q.push(2));
    assert(q.push(3));
    assert(q.push(4));
    assert(!q.push(5));  // full

    int val;
    q.pop(val);
    assert(q.push(5));  // now there's room
}

// =========================================================================
// Main
// =========================================================================
int main() {
    std::cout << "=== GraphEngine Tests ===" << std::endl;
    // Tests are auto-registered and run via static constructors above.
    std::cout << "=== All GraphEngine tests passed ===" << std::endl;
    return 0;
}
