/**
 * @file  test_memory_pool.cpp
 * @brief PoolAllocator C++ 单元测试
 *
 * 编译：cmake --build . --target test_memory_pool
 * 运行：./test_memory_pool
 */

#include "memory_pool.h"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>

#define TEST(name) \
    static void test_##name(); \
    struct Register_##name { \
        Register_##name() { std::cout << "  [RUN] " #name << std::endl; test_##name(); std::cout << "  [PASS] " #name << std::endl; } \
    } reg_##name; \
    static void test_##name()

// =========================================================================
// Test 1: Basic allocation and 64-byte alignment
// =========================================================================
TEST(alloc_and_alignment) {
    mp::FeatureVectorPool pool(8);

    void* p1 = pool.acquire();
    void* p2 = pool.acquire();
    void* p3 = pool.acquire();

    assert(reinterpret_cast<std::uintptr_t>(p1) % 64 == 0);
    assert(reinterpret_cast<std::uintptr_t>(p2) % 64 == 0);
    assert(reinterpret_cast<std::uintptr_t>(p3) % 64 == 0);

    assert(p1 != p2);
    assert(p2 != p3);

    auto s = pool.stats();
    assert(s.used_blocks == 3);
    assert(s.free_blocks == 5);
    assert(s.total_blocks == 8);

    pool.release(p1);
    pool.release(p2);
    pool.release(p3);
}

// =========================================================================
// Test 2: Free-list reuse after release
// =========================================================================
TEST(free_list_reuse) {
    mp::FeatureVectorPool pool(4);

    void* p1 = pool.acquire();
    void* p2 = pool.acquire();
    void* p3 = pool.acquire();

    pool.release(p2);
    auto s1 = pool.stats();
    assert(s1.free_blocks == 2);

    void* p4 = pool.acquire();
    // p4 should be p2 (reused from free list)
    assert(p4 == p2);

    pool.release(p1);
    pool.release(p3);
    pool.release(p4);
}

// =========================================================================
// Test 3: Data integrity -- write and read back
// =========================================================================
TEST(data_integrity) {
    mp::FeatureVectorPool pool(2);
    float* block = static_cast<float*>(pool.acquire());

    for (std::size_t i = 0; i < 128; ++i) {
        block[i] = static_cast<float>(i) * 3.14f;
    }

    for (std::size_t i = 0; i < 128; ++i) {
        assert(block[i] == static_cast<float>(i) * 3.14f);
    }

    pool.release(block);
}

// =========================================================================
// Test 4: Dynamic expansion when pool is exhausted
// =========================================================================
TEST(dynamic_expansion) {
    mp::FeatureVectorPool pool(2);

    void* p1 = pool.acquire();
    void* p2 = pool.acquire();
    assert(pool.stats().total_blocks == 2);

    // This should trigger dynamic expansion
    void* p3 = pool.acquire();
    assert(pool.stats().total_blocks == 3);
    assert(reinterpret_cast<std::uintptr_t>(p3) % 64 == 0);

    pool.release(p1);
    pool.release(p2);
    pool.release(p3);
}

// =========================================================================
// Test 5: Batch allocation stress test
// =========================================================================
TEST(batch_alloc_release) {
    mp::FeatureVectorPool pool(0);
    constexpr std::size_t N = 1000;

    std::vector<void*> ptrs;
    ptrs.reserve(N);
    for (std::size_t i = 0; i < N; ++i) {
        ptrs.push_back(pool.acquire());
    }
    assert(pool.stats().used_blocks == N);

    for (auto* p : ptrs) {
        pool.release(p);
    }
    assert(pool.stats().used_blocks == 0);
    assert(pool.stats().free_blocks == N);
}

// =========================================================================
// Test 6: Stats consistency
// =========================================================================
TEST(stats_consistency) {
    mp::FeatureVectorPool pool(10);

    auto s0 = pool.stats();
    assert(s0.total_blocks == 10);
    assert(s0.used_blocks == 0);
    assert(s0.free_blocks == 10);
    assert(s0.total_bytes_allocated == 10 * 512);
    assert(s0.current_bytes_in_use == 0);

    void* p = pool.acquire();
    auto s1 = pool.stats();
    assert(s1.used_blocks == 1);
    assert(s1.current_bytes_in_use == 512);

    pool.release(p);
    auto s2 = pool.stats();
    assert(s2.used_blocks == 0);
    assert(s2.current_bytes_in_use == 0);
}

// =========================================================================
// Test 7: Move semantics
// =========================================================================
TEST(move_semantics) {
    mp::FeatureVectorPool pool1(4);
    void* p = pool1.acquire();
    assert(pool1.stats().used_blocks == 1);

    // Move construct
    mp::FeatureVectorPool pool2(std::move(pool1));
    assert(pool2.stats().used_blocks == 1);
    assert(pool1.stats().used_blocks == 0);

    pool2.release(p);
}

// =========================================================================
// Test 8: Exception on invalid release
// =========================================================================
TEST(invalid_release_throws) {
    mp::FeatureVectorPool pool(2);
    bool caught = false;
    try {
        pool.release(nullptr);
    } catch (const mp::InvalidBlockException& e) {
        caught = true;
    }
    assert(caught);

    caught = false;
    int dummy;
    try {
        pool.release(&dummy);
    } catch (const mp::InvalidBlockException& e) {
        caught = true;
    }
    assert(caught);
}

// =========================================================================
// Test 9: Zero initial capacity
// =========================================================================
TEST(zero_capacity) {
    mp::FeatureVectorPool pool(0);
    assert(pool.stats().total_blocks == 0);

    void* p = pool.acquire();
    assert(pool.stats().total_blocks == 1);
    assert(reinterpret_cast<std::uintptr_t>(p) % 64 == 0);

    pool.release(p);
}

// =========================================================================
// Main
// =========================================================================
int main() {
    std::cout << "=== PoolAllocator Tests ===" << std::endl;
    // Tests are auto-registered and run via static constructors above.
    std::cout << "=== All PoolAllocator tests passed ===" << std::endl;
    return 0;
}
