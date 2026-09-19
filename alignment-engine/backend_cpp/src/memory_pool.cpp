/**
 * @file  memory_pool.cpp
 * @brief PoolAllocator 的显式实例化与运行时自检
 *
 * 显式实例化确保编译器在本编译单元生成完整的模板代码，
 * 避免链接时出现 undefined reference。
 * 运行时自检在模块加载时验证对齐和分配正确性。
 */

#include "memory_pool.h"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>

// ══════════════════════════════════════════════════════════════
// 显式实例化
// ══════════════════════════════════════════════════════════════

template class mp::PoolAllocator<64, 512>;    ///< 128 维 float 特征向量
template class mp::PoolAllocator<64, 1024>;   ///< 128 维 double 特征向量
template class mp::PoolAllocator<32, 256>;    ///< 64 维 float 特征向量
template class mp::PoolAllocator<64, 4096>;   ///< 大块分配
template class mp::PoolAllocator<128, 512>;   ///< 128B 对齐（AVX-512 预留）

// ══════════════════════════════════════════════════════════════
// 运行时自检（模块加载时执行）
// ══════════════════════════════════════════════════════════════

namespace {

/**
 * @brief 自检函数：验证对齐、分配/释放、统计一致性
 *
 * 在模块加载时（静态初始化阶段）自动执行。
 * 如果任何断言失败，说明内存池实现存在 bug。
 */
struct PoolSelfTest {
    PoolSelfTest() {
        // 测试 1：基本分配与对齐
        {
            mp::FeatureVectorPool pool(4);
            void* p1 = pool.acquire();
            void* p2 = pool.acquire();
            void* p3 = pool.acquire();

            // 验证 64 字节对齐
            assert(reinterpret_cast<std::uintptr_t>(p1) % 64 == 0);
            assert(reinterpret_cast<std::uintptr_t>(p2) % 64 == 0);
            assert(reinterpret_cast<std::uintptr_t>(p3) % 64 == 0);

            // 验证指针互不相同
            assert(p1 != p2);
            assert(p2 != p3);
            assert(p1 != p3);

            // 验证统计
            auto s = pool.stats();
            assert(s.used_blocks == 3);
            assert(s.free_blocks == 1);
            assert(s.total_blocks == 4);

            // 释放 + 重新分配（验证自由链表复用）
            pool.release(p2);
            s = pool.stats();
            assert(s.used_blocks == 2);
            assert(s.free_blocks == 2);

            void* p4 = pool.acquire();
            assert(reinterpret_cast<std::uintptr_t>(p4) % 64 == 0);
            s = pool.stats();
            assert(s.used_blocks == 3);
            assert(s.free_blocks == 1);
        }

        // 测试 2：写入/读取完整性
        {
            mp::FeatureVectorPool pool(1);
            float* block = static_cast<float*>(pool.acquire());
            // 写入 128 个 float
            for (std::size_t i = 0; i < 128; ++i) {
                block[i] = static_cast<float>(i) * 1.5f;
            }
            // 读回验证
            for (std::size_t i = 0; i < 128; ++i) {
                assert(block[i] == static_cast<float>(i) * 1.5f);
            }
            pool.release(block);
        }

        // 测试 3：批量分配与释放
        {
            mp::FeatureVectorPool pool(0);
            constexpr std::size_t N = 100;
            std::vector<void*> ptrs;
            ptrs.reserve(N);
            for (std::size_t i = 0; i < N; ++i) {
                ptrs.push_back(pool.acquire());
            }
            assert(pool.stats().used_blocks == N);
            assert(pool.stats().total_blocks == N);

            for (auto* p : ptrs) {
                pool.release(p);
            }
            assert(pool.stats().used_blocks == 0);
            assert(pool.stats().free_blocks == N);
        }
    }
} g_pool_self_test;

}  // anonymous namespace
