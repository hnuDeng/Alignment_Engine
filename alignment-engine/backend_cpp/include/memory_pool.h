/**
 * @file  memory_pool.h
 * @brief SIMD 对齐内存池分配器 —— 用于 128 维浮点特征向量的高频分配
 *
 * 设计目标：
 *  1. 所有分配块严格 64 字节对齐，兼容 AVX2 _mm256_load_ps/_mm256_store_ps
 *  2. 通过自由链表复用已释放块，消除 new/delete 导致的内存碎片
 *  3. O(1) 分配/释放（自由链表非空时），O(capacity) 仅在首次扩展时
 *  4. 整个池的内存在析构时一次性释放，避免逐块 free 开销
 *
 * 内存布局（capacity 个连续块）：
 *  ┌──────────┬──────────┬──────────┬─────┬──────────┐
 *  │ Block #0 │ Block #1 │ Block #2 │ ... │ Block #N │
 *  └──────────┴──────────┴──────────┴─────┴──────────┘
 *  每个块大小 = block_size_ 字节，对齐 = alignment_ 字节
 *  底层通过 _aligned_malloc (Windows) / aligned_alloc (POSIX) 分配
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace mp {

// ── 常量 ──────────────────────────────────────────────────────
inline constexpr std::size_t kSimdAlignment     = 64;   ///< AVX2 缓存行对齐
inline constexpr std::size_t kDefaultBlockSize  = 512;  ///< 128 * sizeof(float)
inline constexpr std::size_t kDefaultInitCap    = 1024; ///< 初始预留块数

/**
 * @brief 内存池统计快照
 *
 * 用于运行时监控池的使用状况，
 * 可通过 Python 的 pybind11 桥接暴露给上层。 */
struct PoolStats {
    std::size_t total_bytes_allocated;   ///< 底层总分配字节数
    std::size_t current_bytes_in_use;    ///< 当前正在使用的字节数
    std::size_t total_blocks;            ///< 已分配块总数
    std::size_t free_blocks;             ///< 空闲链表中的块数
    std::size_t used_blocks;             ///< 正在使用的块数
};

// ══════════════════════════════════════════════════════════════
// 自定义异常层级
// ══════════════════════════════════════════════════════════════

class MemoryPoolException : public std::runtime_error {
public:
    explicit MemoryPoolException(const std::string& msg)
        : std::runtime_error("[MemoryPool] " + msg) {}
};

class AlignmentException : public MemoryPoolException {
public:
    explicit AlignmentException(std::size_t requested, std::size_t actual)
        : MemoryPoolException(
              "Alignment violation: requested=" + std::to_string(requested) +
              ", got=" + std::to_string(actual)) {}
};

class PoolExhaustedException : public MemoryPoolException {
public:
    explicit PoolExhaustedException(std::size_t capacity, std::size_t block_size)
        : MemoryPoolException(
              "Pool exhausted: capacity=" + std::to_string(capacity) +
              ", block_size=" + std::to_string(block_size) + " bytes") {}
};

class InvalidBlockException : public MemoryPoolException {
public:
    explicit InvalidBlockException(std::size_t block_index, std::size_t capacity)
        : MemoryPoolException(
              "Invalid block index=" + std::to_string(block_index) +
              ", capacity=" + std::to_string(capacity)) {}
};

// ══════════════════════════════════════════════════════════════
// PoolAllocator 模板类
// ══════════════════════════════════════════════════════════════

/**
 * @brief 固定块大小的 SIMD 对齐内存池
 *
 * @tparam Alignment   对齐字节数，必须是 2 的幂且 >= 16（默认 64）
 * @tparam BlockSize   每个块的字节数（默认 512 = 128 * sizeof(float)）
 *
 * 不变量：
 *  - 每个分配的指针满足 (uintptr_t)ptr % Alignment == 0
 *  - free_list_ 中的索引均在 [0, capacity_) 范围内
 *  - used_count_ + free_list_.size() == total_blocks_
 */
template <std::size_t Alignment = kSimdAlignment,
          std::size_t BlockSize = kDefaultBlockSize>
class PoolAllocator {
public:
    static_assert((Alignment & (Alignment - 1)) == 0,
                  "Alignment must be a power of 2");
    static_assert(Alignment >= 16,
                  "Alignment must be >= 16 for SSE/AVX");
    static_assert(BlockSize > 0,
                  "BlockSize must be > 0");

    /**
     * @brief 构造并预分配 initial_capacity 个块
     * @param initial_capacity  初始块数
     * @throws AlignmentException  如果平台不支持所需对齐
     */
    explicit PoolAllocator(std::size_t initial_capacity = kDefaultInitCap);

    ~PoolAllocator();

    // 禁止拷贝，允许移动
    PoolAllocator(const PoolAllocator&)            = delete;
    PoolAllocator& operator=(const PoolAllocator&) = delete;
    PoolAllocator(PoolAllocator&& other) noexcept;
    PoolAllocator& operator=(PoolAllocator&& other) noexcept;

    /**
     * @brief 分配一个对齐块
     * @return 块的起始指针（alignment_ 字节对齐）
     * @throws PoolExhaustedException  如果扩展分配失败
     *
     * 时间复杂度：
     *  - 自由链表非空：O(1) 弹出栈顶
     *  - 自由链表为空：O(1) 在末尾追加新块（触发 realloc 时摊还 O(capacity)）
     */
    void* acquire();

    /**
     * @brief 释放一个对齐块，归还到自由链表
     * @param ptr  由 acquire() 返回的指针
     * @throws InvalidBlockException  如果 ptr 不属于本池
     *
     * 时间复杂度：O(1) 验证 + O(1) 压入栈顶
     */
    void release(void* ptr);

    /**
     * @brief 获取统计快照
     *
     * 时间复杂度：O(1)
     */
    [[nodiscard]] PoolStats stats() const noexcept;

    [[nodiscard]] std::size_t capacity() const noexcept  { return capacity_; }
    [[nodiscard]] std::size_t block_size() const noexcept { return BlockSize; }
    [[nodiscard]] std::size_t alignment() const noexcept  { return Alignment; }

    /**
     * @brief 手动扩展池容量
     * @param additional_blocks  额外添加的块数
     * @throws PoolExhaustedException  如果对齐分配失败
     */
    void reserve(std::size_t additional_blocks);

private:
    /// 底层内存块数组：blocks_[i] 指向第 i 个块的起始地址
    std::vector<void*> blocks_;
    /// 自由链表：存储可用块的索引（栈结构，O(1) push/pop）
    std::vector<std::size_t> free_list_;
    /// 当前已分配的块数（包括在使用和空闲的）
    std::size_t capacity_;
    /// 正在使用的块数
    std::size_t used_count_;

    /**
     * @brief 分配一个新的对齐内存块
     * @return 块的起始指针
     * @throws AlignmentException    如果对齐分配失败
     * @throws PoolExhaustedException 如果底层分配失败
     */
    void* allocate_aligned_block();

    /**
     * @brief 释放一个对齐内存块
     * @param ptr  由 allocate_aligned_block() 返回的指针
     */
    void deallocate_aligned_block(void* ptr) noexcept;

    /**
     * @brief 获取第 index 个块的指针
     * @throws InvalidBlockException 如果 index >= capacity_
     */
    [[nodiscard]] void* block_at(std::size_t index) const;
};

// ── 便捷类型别名 ────────────────────────────────────────────

/// 128 维 float 特征向量分配器（对齐 64B，块大小 512B）
using FeatureVectorPool = PoolAllocator<kSimdAlignment, 128 * sizeof(float)>;

/// 128 维 double 特征向量分配器（对齐 64B，块大小 1024B）
using FeatureVectorPoolD = PoolAllocator<kSimdAlignment, 128 * sizeof(double)>;

}  // namespace mp

// ══════════════════════════════════════════════════════════════
// 模板实现（必须在头文件中，因为是模板）
// ══════════════════════════════════════════════════════════════

template <std::size_t Alignment, std::size_t BlockSize>
mp::PoolAllocator<Alignment, BlockSize>::PoolAllocator(
    std::size_t initial_capacity)
    : capacity_(0), used_count_(0)
{
    if (initial_capacity > 0) {
        blocks_.reserve(initial_capacity);
        free_list_.reserve(initial_capacity);
        reserve(initial_capacity);
    }
}

template <std::size_t Alignment, std::size_t BlockSize>
mp::PoolAllocator<Alignment, BlockSize>::~PoolAllocator()
{
    for (std::size_t i = 0; i < blocks_.size(); ++i) {
        deallocate_aligned_block(blocks_[i]);
    }
    blocks_.clear();
    free_list_.clear();
    capacity_   = 0;
    used_count_ = 0;
}

template <std::size_t Alignment, std::size_t BlockSize>
mp::PoolAllocator<Alignment, BlockSize>::PoolAllocator(
    PoolAllocator&& other) noexcept
    : blocks_(std::move(other.blocks_)),
      free_list_(std::move(other.free_list_)),
      capacity_(other.capacity_),
      used_count_(other.used_count_)
{
    other.capacity_   = 0;
    other.used_count_ = 0;
}

template <std::size_t Alignment, std::size_t BlockSize>
mp::PoolAllocator<Alignment, BlockSize>&
mp::PoolAllocator<Alignment, BlockSize>::operator=(
    PoolAllocator&& other) noexcept
{
    if (this != &other) {
        // 释放已有内存
        for (std::size_t i = 0; i < blocks_.size(); ++i) {
            deallocate_aligned_block(blocks_[i]);
        }
        blocks_    = std::move(other.blocks_);
        free_list_ = std::move(other.free_list_);
        capacity_  = other.capacity_;
        used_count_ = other.used_count_;
        other.capacity_   = 0;
        other.used_count_ = 0;
    }
    return *this;
}

template <std::size_t Alignment, std::size_t BlockSize>
void* mp::PoolAllocator<Alignment, BlockSize>::acquire()
{
    // 优先从自由链表复用
    if (!free_list_.empty()) {
        std::size_t idx = free_list_.back();
        free_list_.pop_back();
        ++used_count_;
        return blocks_[idx];
    }

    // 自由链表为空 → 扩展池
    void* ptr = allocate_aligned_block();
    blocks_.push_back(ptr);
    ++capacity_;
    ++used_count_;
    return ptr;
}

template <std::size_t Alignment, std::size_t BlockSize>
void mp::PoolAllocator<Alignment, BlockSize>::release(void* ptr)
{
    if (ptr == nullptr) {
        throw InvalidBlockException(0, capacity_);
    }

    // 线性扫描查找块索引（块数通常 < 100k，可接受）
    for (std::size_t i = 0; i < blocks_.size(); ++i) {
        if (blocks_[i] == ptr) {
            free_list_.push_back(i);
            --used_count_;
            return;
        }
    }

    throw InvalidBlockException(0, capacity_);
}

template <std::size_t Alignment, std::size_t BlockSize>
mp::PoolStats mp::PoolAllocator<Alignment, BlockSize>::stats() const noexcept
{
    return PoolStats{
        .total_bytes_allocated = capacity_ * BlockSize,
        .current_bytes_in_use  = used_count_ * BlockSize,
        .total_blocks          = capacity_,
        .free_blocks           = free_list_.size(),
        .used_blocks           = used_count_
    };
}

template <std::size_t Alignment, std::size_t BlockSize>
void mp::PoolAllocator<Alignment, BlockSize>::reserve(
    std::size_t additional_blocks)
{
    blocks_.reserve(capacity_ + additional_blocks);
    free_list_.reserve(free_list_.size() + additional_blocks);

    for (std::size_t i = 0; i < additional_blocks; ++i) {
        void* ptr = allocate_aligned_block();
        blocks_.push_back(ptr);
        free_list_.push_back(capacity_);
        ++capacity_;
    }
}

template <std::size_t Alignment, std::size_t BlockSize>
void* mp::PoolAllocator<Alignment, BlockSize>::allocate_aligned_block()
{
#ifdef _WIN32
    void* ptr = _aligned_malloc(BlockSize, Alignment);
    if (ptr == nullptr) {
        throw PoolExhaustedException(capacity_, BlockSize);
    }
#else
    void* ptr = std::aligned_alloc(Alignment, BlockSize);
    if (ptr == nullptr) {
        throw PoolExhaustedException(capacity_, BlockSize);
    }
#endif

    // 验证对齐
    if (reinterpret_cast<std::uintptr_t>(ptr) % Alignment != 0) {
        deallocate_aligned_block(ptr);
        throw AlignmentException(
            Alignment, reinterpret_cast<std::uintptr_t>(ptr) % Alignment);
    }

    return ptr;
}

template <std::size_t Alignment, std::size_t BlockSize>
void mp::PoolAllocator<Alignment, BlockSize>::deallocate_aligned_block(
    void* ptr) noexcept
{
    if (ptr == nullptr) return;
#ifdef _WIN32
    _aligned_free(ptr);
#else
    std::free(ptr);
#endif
}

template <std::size_t Alignment, std::size_t BlockSize>
void* mp::PoolAllocator<Alignment, BlockSize>::block_at(
    std::size_t index) const
{
    if (index >= capacity_) {
        throw InvalidBlockException(index, capacity_);
    }
    return blocks_[index];
}
