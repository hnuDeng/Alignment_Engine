/**
 * @file  test_feature_graph.cpp
 * @brief C++ 原生测试 —— 验证 FeatureGraph 和 DriftDetector 的核心逻辑
 *
 * 编译方式（不依赖 GoogleTest，自包含断言）：
 *   cmake -DBUILD_TESTS=ON .. && cmake --build .
 *   ./test_feature_graph
 */

#include "drift_detector.h"
#include "feature_graph.h"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <iostream>
#include <numeric>
#include <random>
#include <vector>

// ── 简易测试框架 ─────────────────────────────────────────────
static int tests_passed = 0;
static int tests_failed = 0;

#define TEST_ASSERT(cond, msg)                                      \
    do {                                                            \
        if (!(cond)) {                                              \
            std::cerr << "FAIL: " << __func__ << ": " << msg       \
                      << " [" << __FILE__ << ":" << __LINE__ << "]"\
                      << std::endl;                                 \
            ++tests_failed;                                         \
            return;                                                 \
        }                                                           \
    } while (0)

#define TEST_PASS()                                                 \
    do { std::cout << "PASS: " << __func__ << std::endl;           \
         ++tests_passed; } while (0)

// ══════════════════════════════════════════════════════════════
// 辅助函数
// ══════════════════════════════════════════════════════════════

static std::vector<double> random_embedding(std::size_t dim, double mean, std::mt19937& rng) {
    std::normal_distribution<double> dist(mean, 1.0);
    std::vector<double> emb(dim);
    for (auto& v : emb) v = dist(rng);
    return emb;
}

// ══════════════════════════════════════════════════════════════
// 测试用例
// ══════════════════════════════════════════════════════════════

void test_graph_construction() {
    fg::FeatureGraph<double> g(128);
    TEST_ASSERT(g.size() == 0, "empty graph size");
    TEST_ASSERT(g.embedding_dim() == 128, "embedding dim");

    std::vector<double> emb(128, 0.5);
    g.add_node(1, 0, emb);
    TEST_ASSERT(g.size() == 1, "size after add");
    TEST_ASSERT(g.node(0).id == 1, "node id");

    TEST_PASS();
}

void test_invalid_embedding_dim() {
    fg::FeatureGraph<double> g(64);
    std::vector<double> wrong_dim(32, 0.0);
    bool caught = false;
    try {
        g.add_node(1, 0, wrong_dim);
    } catch (const std::invalid_argument&) {
        caught = true;
    }
    TEST_ASSERT(caught, "should throw on wrong embedding dim");
    TEST_PASS();
}

void test_centroid_distances() {
    fg::FeatureGraph<double> g(4);

    // 节点 0: [0, 0, 0, 0]
    g.add_node(0, 0, {0, 0, 0, 0});
    // 节点 1: [1, 1, 1, 1]
    g.add_node(1, 0, {1, 1, 1, 1});
    // 节点 2: [10, 10, 10, 10]  → 明显远离
    g.add_node(2, 1, {10, 10, 10, 10});

    g.compute_centroid_distances();

    // 质心 ≈ (11/3, 11/3, 11/3, 11/3)
    // 节点 2 到质心的距离应远大于节点 0 和 1
    double d0 = g.node(0).dist_sq_to_centroid;
    double d2 = g.node(2).dist_sq_to_centroid;
    TEST_ASSERT(d2 > d0, "outlier should have larger dist_sq_to_centroid");

    TEST_PASS();
}

void test_top_outliers() {
    fg::FeatureGraph<double> g(4);
    g.add_node(0, 0, {0, 0, 0, 0});
    g.add_node(1, 0, {1, 1, 1, 1});
    g.add_node(2, 1, {100, 100, 100, 100});
    g.add_node(3, 1, {50, 50, 50, 50});

    g.compute_centroid_distances();
    auto outliers = g.top_outliers(2);

    TEST_ASSERT(outliers.size() == 2, "should return 2 outliers");
    TEST_ASSERT(outliers[0] == 2, "most distant should be node 2");
    TEST_ASSERT(outliers[1] == 3, "second most distant should be node 3");

    TEST_PASS();
}

void test_bfs_isolation() {
    fg::FeatureGraph<double> g(4);

    // 紧密簇
    g.add_node(0, 0, {0.0, 0.0, 0.0, 0.0});
    g.add_node(1, 0, {0.1, 0.1, 0.1, 0.1});
    g.add_node(2, 0, {0.2, 0.0, 0.0, 0.0});

    // 孤立节点
    g.add_node(3, 1, {100.0, 100.0, 100.0, 100.0});

    g.compute_centroid_distances();
    g.build_adjacency_graph(5.0);  // 阈值 5.0 → 孤立节点不会被连接

    auto results = g.bfs_isolation_score(2, 10);

    TEST_ASSERT(results.size() == 4, "should have 4 results");

    // 最高孤立度分数应属于节点 3（距质心最远，不在邻接图中）
    // 找到节点 3 的分数
    double isolation_3 = 0;
    for (const auto& [idx, score] : results) {
        if (g.node(idx).id == 3) {
            isolation_3 = score;
            break;
        }
    }
    TEST_ASSERT(isolation_3 > 0, "node 3 should have positive isolation score");
    // 节点 3 应在结果的最高分位置（或接近最高）
    TEST_ASSERT(results[0].second >= isolation_3 ||
                isolation_3 == 11.0,  // max_hops + 1
                "node 3 should be among the most isolated");

    TEST_PASS();
}

void test_batch_add() {
    fg::FeatureGraph<double> g(4);
    std::vector<uint32_t> ids = {0, 1, 2};
    std::vector<uint32_t> labels = {0, 1, 0};
    std::vector<std::vector<double>> embs = {
        {0, 0, 0, 0},
        {1, 1, 1, 1},
        {2, 2, 2, 2},
    };

    g.add_nodes_batch(ids, labels, embs);
    TEST_ASSERT(g.size() == 3, "batch add size");

    TEST_PASS();
}

void test_drift_detector() {
    // 构造 8 个正常样本 + 2 个明显异常样本
    std::mt19937 rng(42);
    const std::size_t n_normal  = 8;
    const std::size_t n_outlier = 2;
    const std::size_t n = n_normal + n_outlier;
    const std::size_t dim = 32;

    std::vector<uint32_t> ids(n);
    std::vector<uint32_t> labels(n);
    std::vector<std::vector<double>> embeddings(n);

    for (std::size_t i = 0; i < n_normal; ++i) {
        ids[i] = static_cast<uint32_t>(i);
        labels[i] = 0;
        embeddings[i] = random_embedding(dim, 0.0, rng);
    }
    for (std::size_t i = 0; i < n_outlier; ++i) {
        ids[n_normal + i] = static_cast<uint32_t>(n_normal + i);
        labels[n_normal + i] = 1;
        embeddings[n_normal + i] = random_embedding(dim, 50.0, rng);
    }

    fg::DriftDetector detector(dim, 2.0, 3, 3, 10, 15.0);
    auto result = detector.detect(ids, labels, embeddings);

    TEST_ASSERT(result.outlier_ids.size() >= 1, "should detect at least 1 outlier");
    TEST_ASSERT(result.outlier_ids.size() <= 3, "should not exceed max_outliers=3");
    TEST_ASSERT(result.mean_distance > 0, "mean_distance should be positive");
    TEST_ASSERT(result.threshold > result.mean_distance,
                "threshold should be > mean_distance");

    // 异常样本的 ID 应属于高 ID 段（50.0 均值的那些）
    for (uint32_t oid : result.outlier_ids) {
        TEST_ASSERT(oid >= n_normal,
                    "outlier ID should be from the outlier group");
    }

    TEST_PASS();
}

void test_drift_detector_flat_interface() {
    std::vector<uint32_t> ids    = {0, 1, 2, 3};
    std::vector<uint32_t> labels = {0, 0, 0, 1};
    // 4 个 8 维样本，扁平化
    std::vector<double> flat = {
        0, 0, 0, 0, 0, 0, 0, 0,    // sample 0
        1, 1, 1, 1, 1, 1, 1, 1,    // sample 1
        2, 2, 2, 2, 2, 2, 2, 2,    // sample 2
        100, 100, 100, 100, 100, 100, 100, 100,  // sample 3 (outlier)
    };

    fg::DriftDetector detector(8, 2.0, 2, 2, 5, 10.0);
    auto result = detector.detect(ids, labels, flat);

    TEST_ASSERT(result.outlier_ids.size() >= 1, "should detect outlier via flat API");
    TEST_PASS();
}

void test_clear_and_reuse() {
    fg::FeatureGraph<double> g(4);
    g.add_node(0, 0, {0, 0, 0, 0});
    g.add_node(1, 0, {1, 1, 1, 1});
    TEST_ASSERT(g.size() == 2, "size before clear");

    g.clear();
    TEST_ASSERT(g.size() == 0, "size after clear");

    g.add_node(10, 1, {5, 5, 5, 5});
    TEST_ASSERT(g.size() == 1, "size after reuse");
    TEST_ASSERT(g.node(0).id == 10, "reused node id");

    TEST_PASS();
}

// ══════════════════════════════════════════════════════════════
// 主函数
// ══════════════════════════════════════════════════════════════

int main() {
    std::cout << "=== FeatureGraph Engine C++ Tests ===" << std::endl;

    test_graph_construction();
    test_invalid_embedding_dim();
    test_centroid_distances();
    test_top_outliers();
    test_bfs_isolation();
    test_batch_add();
    test_drift_detector();
    test_drift_detector_flat_interface();
    test_clear_and_reuse();

    std::cout << "\n=== Results: " << tests_passed << " passed, "
              << tests_failed << " failed ===" << std::endl;

    return tests_failed > 0 ? 1 : 0;
}
