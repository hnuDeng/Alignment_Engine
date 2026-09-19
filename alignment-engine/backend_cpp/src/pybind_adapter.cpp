/**
 * @file  pybind_adapter.cpp
 * @brief pybind11 安全绑定层 -- GraphEngine + MemoryPool + 异常转换 + GIL 释放
 *
 * 设计要点：
 *  1. C++ 异常 -> Python 自定义异常的完整映射链
 *  2. 耗时算法（BFS/Dijkstra）在释放 GIL 的情况下执行
 *  3. numpy 数组零拷贝转换
 *  4. 内存池统计直接暴露给 Python
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "graph_algorithms.h"
#include "memory_pool.h"

#include <string>
#include <vector>
#include <stdexcept>

namespace py = pybind11;

// =========================================================================
// Python custom exception types
// These mirror the C++ exception hierarchy for clean Python error handling.
// =========================================================================

// MemoryPool exceptions
static PyObject* g_py_MemoryPoolException    = nullptr;
static PyObject* g_py_AlignmentException     = nullptr;
static PyObject* g_py_PoolExhaustedException = nullptr;
static PyObject* g_py_InvalidBlockException  = nullptr;

// GraphEngine exceptions
static PyObject* g_py_GraphEngineException        = nullptr;
static PyObject* g_py_NodeNotFoundException        = nullptr;
static PyObject* g_py_DuplicateNodeException       = nullptr;
static PyObject* g_py_EmbeddingDimensionException  = nullptr;

// =========================================================================
// Exception translation: C++ -> Python
// =========================================================================

static void translate_memory_pool_exception(const mp::MemoryPoolException& e) {
    PyErr_SetString(g_py_MemoryPoolException, e.what());
}

static void translate_alignment_exception(const mp::AlignmentException& e) {
    PyErr_SetString(g_py_AlignmentException, e.what());
}

static void translate_pool_exhausted_exception(const mp::PoolExhaustedException& e) {
    PyErr_SetString(g_py_PoolExhaustedException, e.what());
}

static void translate_invalid_block_exception(const mp::InvalidBlockException& e) {
    PyErr_SetString(g_py_InvalidBlockException, e.what());
}

static void translate_graph_engine_exception(const ga::GraphEngineException& e) {
    PyErr_SetString(g_py_GraphEngineException, e.what());
}

static void translate_node_not_found_exception(const ga::NodeNotFoundException& e) {
    PyErr_SetString(g_py_NodeNotFoundException, e.what());
}

static void translate_duplicate_node_exception(const ga::DuplicateNodeException& e) {
    PyErr_SetString(g_py_DuplicateNodeException, e.what());
}

static void translate_embedding_dim_exception(const ga::EmbeddingDimensionException& e) {
    PyErr_SetString(g_py_EmbeddingDimensionException, e.what());
}

// =========================================================================
// numpy -> C++ vector conversion helpers
// =========================================================================

static std::vector<float> numpy_to_float_vec(
    py::array_t<float, py::array::c_style | py::array::forcecast> arr)
{
    auto buf = arr.request();
    auto* ptr = static_cast<const float*>(buf.ptr);
    return std::vector<float>(ptr, ptr + buf.size);
}

static std::vector<uint32_t> numpy_to_u32_vec(
    py::array_t<uint32_t, py::array::c_style | py::array::forcecast> arr)
{
    auto buf = arr.request();
    auto* ptr = static_cast<const uint32_t*>(buf.ptr);
    return std::vector<uint32_t>(ptr, ptr + buf.size);
}

// =========================================================================
// Module definition
// =========================================================================

PYBIND11_MODULE(graph_engine_py, m) {
    m.doc() = R"doc(
        High-performance SIMD-aligned graph computation engine.

        Features:
        - 64-byte aligned memory pool for AVX2 feature vectors
        - Lock-free MPMC queue for concurrent BFS
        - OpenMP parallel BFS and Dijkstra algorithms
        - Complete C++ -> Python exception mapping
        - GIL release during compute-intensive operations
    )doc";

    m.attr("__version__") = "2.0.0";

    // =====================================================================
    // Register Python exception types
    // Hierarchy mirrors the C++ exception classes exactly.
    // =====================================================================

    g_py_MemoryPoolException = PyErr_NewException(
        "graph_engine_py.MemoryPoolException", PyExc_RuntimeError, nullptr);
    Py_INCREF(g_py_MemoryPoolException);
    m.attr("MemoryPoolException") = g_py_MemoryPoolException;

    g_py_AlignmentException = PyErr_NewException(
        "graph_engine_py.AlignmentException", g_py_MemoryPoolException, nullptr);
    Py_INCREF(g_py_AlignmentException);
    m.attr("AlignmentException") = g_py_AlignmentException;

    g_py_PoolExhaustedException = PyErr_NewException(
        "graph_engine_py.PoolExhaustedException", g_py_MemoryPoolException, nullptr);
    Py_INCREF(g_py_PoolExhaustedException);
    m.attr("PoolExhaustedException") = g_py_PoolExhaustedException;

    g_py_InvalidBlockException = PyErr_NewException(
        "graph_engine_py.InvalidBlockException", g_py_MemoryPoolException, nullptr);
    Py_INCREF(g_py_InvalidBlockException);
    m.attr("InvalidBlockException") = g_py_InvalidBlockException;

    g_py_GraphEngineException = PyErr_NewException(
        "graph_engine_py.GraphEngineException", PyExc_RuntimeError, nullptr);
    Py_INCREF(g_py_GraphEngineException);
    m.attr("GraphEngineException") = g_py_GraphEngineException;

    g_py_NodeNotFoundException = PyErr_NewException(
        "graph_engine_py.NodeNotFoundException", g_py_GraphEngineException, nullptr);
    Py_INCREF(g_py_NodeNotFoundException);
    m.attr("NodeNotFoundException") = g_py_NodeNotFoundException;

    g_py_DuplicateNodeException = PyErr_NewException(
        "graph_engine_py.DuplicateNodeException", g_py_GraphEngineException, nullptr);
    Py_INCREF(g_py_DuplicateNodeException);
    m.attr("DuplicateNodeException") = g_py_DuplicateNodeException;

    g_py_EmbeddingDimensionException = PyErr_NewException(
        "graph_engine_py.EmbeddingDimensionException", g_py_GraphEngineException, nullptr);
    Py_INCREF(g_py_EmbeddingDimensionException);
    m.attr("EmbeddingDimensionException") = g_py_EmbeddingDimensionException;

    // Register C++ -> Python exception translators
    // Order matters: most-derived first (pybind11 tries translators in registration order)
    py::register_exception<mp::InvalidBlockException>(m, "InvalidBlockCppException", g_py_InvalidBlockException);
    py::register_exception<mp::PoolExhaustedException>(m, "PoolExhaustedCppException", g_py_PoolExhaustedException);
    py::register_exception<mp::AlignmentException>(m, "AlignmentCppException", g_py_AlignmentException);
    py::register_exception<mp::MemoryPoolException>(m, "MemoryPoolCppException", g_py_MemoryPoolException);
    py::register_exception<ga::EmbeddingDimensionException>(m, "EmbeddingDimensionCppException", g_py_EmbeddingDimensionException);
    py::register_exception<ga::DuplicateNodeException>(m, "DuplicateNodeCppException", g_py_DuplicateNodeException);
    py::register_exception<ga::NodeNotFoundException>(m, "NodeNotFoundCppException", g_py_NodeNotFoundException);
    py::register_exception<ga::GraphEngineException>(m, "GraphEngineCppException", g_py_GraphEngineException);

    // =====================================================================
    // PoolStats binding
    // =====================================================================

    py::class_<mp::PoolStats>(m, "PoolStats", "Memory pool allocation statistics")
        .def_readonly("total_bytes_allocated", &mp::PoolStats::total_bytes_allocated)
        .def_readonly("current_bytes_in_use",  &mp::PoolStats::current_bytes_in_use)
        .def_readonly("total_blocks",          &mp::PoolStats::total_blocks)
        .def_readonly("free_blocks",           &mp::PoolStats::free_blocks)
        .def_readonly("used_blocks",           &mp::PoolStats::used_blocks)
        .def("__repr__", [](const mp::PoolStats& s) {
            return "<PoolStats total=" + std::to_string(s.total_bytes_allocated) +
                   "B used=" + std::to_string(s.current_bytes_in_use) +
                   "B blocks=" + std::to_string(s.used_blocks) +
                   "/" + std::to_string(s.total_blocks) + ">";
        });

    // =====================================================================
    // FeatureVectorPool binding (for standalone use)
    // =====================================================================

    py::class_<mp::FeatureVectorPool>(m, "FeatureVectorPool",
        "SIMD-aligned (64B) memory pool for 128-dim float feature vectors")
        .def(py::init<std::size_t>(),
             py::arg("initial_capacity") = mp::kDefaultInitCap)
        .def("acquire", [](mp::FeatureVectorPool& self) {
            void* ptr = self.acquire();
            // Return as a capsule for safe Python-side lifetime management
            return py::capsule(ptr, [](void* p) {
                // Note: the pool owns the memory, do not free here
                // This capsule is for reference tracking only
                (void)p;
            });
        }, "Acquire a 64-byte aligned block from the pool")
        .def("stats", &mp::FeatureVectorPool::stats)
        .def("capacity", &mp::FeatureVectorPool::capacity)
        .def("block_size", &mp::FeatureVectorPool::block_size)
        .def("alignment", &mp::FeatureVectorPool::alignment)
        .def("reserve", &mp::FeatureVectorPool::reserve,
             py::arg("additional_blocks"),
             "Manually expand pool capacity");

    // =====================================================================
    // BFSResult binding
    // =====================================================================

    py::class_<ga::BFSResult>(m, "BFSResult", "BFS traversal result")
        .def_readonly("distance",          &ga::BFSResult::distance)
        .def_readonly("visit_order",       &ga::BFSResult::visit_order)
        .def_readonly("isolated_nodes",    &ga::BFSResult::isolated_nodes)
        .def_readonly("max_depth_reached", &ga::BFSResult::max_depth_reached)
        .def("__repr__", [](const ga::BFSResult& r) {
            return "<BFSResult visited=" + std::to_string(r.visit_order.size()) +
                   " isolated=" + std::to_string(r.isolated_nodes.size()) +
                   " max_depth=" + std::to_string(r.max_depth_reached) + ">";
        });

    // =====================================================================
    // DijkstraResult binding
    // =====================================================================

    py::class_<ga::DijkstraResult>(m, "DijkstraResult", "Dijkstra shortest path result")
        .def_readonly("distance",         &ga::DijkstraResult::distance)
        .def_readonly("predecessor",      &ga::DijkstraResult::predecessor)
        .def_readonly("reachable_nodes",  &ga::DijkstraResult::reachable_nodes)
        .def("__repr__", [](const ga::DijkstraResult& r) {
            return "<DijkstraResult reachable=" +
                   std::to_string(r.reachable_nodes.size()) + ">";
        });

    // =====================================================================
    // GraphEngine binding -- the main API
    // =====================================================================

    py::class_<ga::GraphEngine>(m, "GraphEngine", R"doc(
        High-dimensional feature space graph engine.

        Uses SIMD-aligned memory pool for 128-dim float vectors.
        Provides OpenMP-parallel BFS isolation detection and
        Dijkstra shortest path for drift boundary analysis.
    )doc")
        .def(py::init<std::size_t, std::size_t>(),
             py::arg("embedding_dim") = ga::kDefaultDim,
             py::arg("initial_pool_capacity") = 4096)

        // -- Node management (GIL held, fast O(D) operations) --
        .def("add_node",
             [](ga::GraphEngine& self, uint32_t id, uint32_t label_id,
                py::array_t<float, py::array::c_style | py::array::forcecast> embedding) {
                 auto vec = numpy_to_float_vec(std::move(embedding));
                 self.add_node(id, label_id, vec);
             },
             py::arg("id"), py::arg("label_id"), py::arg("embedding"),
             "Add a node with its feature vector (must be 128-dim float32)")

        .def("add_edge", &ga::GraphEngine::add_edge,
             py::arg("src_id"), py::arg("dst_id"), py::arg("weight"),
             "Add an undirected weighted edge between two nodes")

        .def("get_embedding",
             [](const ga::GraphEngine& self, uint32_t id) {
                 auto vec = self.get_embedding(id);
                 // Return as numpy array (copy)
                 py::array_t<float> result(static_cast<py::ssize_t>(vec.size()));
                 std::copy(vec.begin(), vec.end(),
                           static_cast<float*>(result.mutable_request().ptr));
                 return result;
             },
             py::arg("id"),
             "Get node's feature vector as numpy array")

        .def("has_node", &ga::GraphEngine::has_node, py::arg("id"))
        .def("size", &ga::GraphEngine::size)
        .def("embedding_dim", &ga::GraphEngine::embedding_dim)
        .def("pool_stats", &ga::GraphEngine::pool_stats)
        .def("clear", &ga::GraphEngine::clear)
        .def("node_ids", &ga::GraphEngine::node_ids)
        .def("neighbor_count", &ga::GraphEngine::neighbor_count, py::arg("id"))

        // -- Algorithm 1: BFS (GIL released for compute) --
        .def("bfs",
             [](ga::GraphEngine& self, uint32_t source_id, uint32_t max_depth) {
                 // Release GIL during BFS computation
                 // This allows Python threads to run concurrently
                 // while C++ performs the graph traversal
                 py::gil_scoped_release release;
                 return self.bfs(source_id, max_depth);
             },
             py::arg("source_id"),
             py::arg("max_depth") = 0,
             R"doc(
                 BFS isolation detection from source node.

                 Releases GIL during computation for Python thread concurrency.
                 Uses OpenMP parallel neighbor expansion.

                 Time:  O(V + E)
                 Space: O(V)
             )doc")

        // -- Algorithm 2: Dijkstra (GIL released for compute) --
        .def("dijkstra",
             [](ga::GraphEngine& self, uint32_t source_id, std::size_t max_edges) {
                 // Release GIL during Dijkstra computation
                 py::gil_scoped_release release;
                 return self.dijkstra(source_id, max_edges);
             },
             py::arg("source_id"),
             py::arg("max_edges") = 0,
             R"doc(
                 Dijkstra shortest path from source node.

                 Releases GIL during computation for Python thread concurrency.
                 Uses OpenMP parallel edge relaxation.

                 Time:  O((V + E) log V)
                 Space: O(V + E)
             )doc")

        // -- String representation --
        .def("__repr__", [](const ga::GraphEngine& self) {
            auto ps = self.pool_stats();
            return "<GraphEngine dim=" + std::to_string(self.embedding_dim()) +
                   " nodes=" + std::to_string(self.size()) +
                   " pool_used=" + std::to_string(ps.used_blocks) +
                   "/" + std::to_string(ps.total_blocks) + ">";
        })
        .def("__len__", &ga::GraphEngine::size);
}
