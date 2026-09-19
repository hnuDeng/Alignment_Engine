/**
 * @file  pybind_wrapper.cpp
 * @brief pybind11 包装器 —— 将 GraphSearch 的全部方法暴露给 Python
 *
 * Python 端用法：
 *   import graph_search_py as gs
 *   g = gs.GraphSearch(embedding_dim=128)
 *   g.add_nodes_batch(ids, labels, embeddings)
 *   dist = g.compute_distance_matrix()
 *   g.build_graph(threshold=15.0, dist_matrix=dist)
 *   iso  = g.bfs_longtail_isolation(k_seeds=5, max_hops=10)
 *   path = g.dp_shortest_distribution_path(sources=[0,1])
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "graph_search.h"

namespace py = pybind11;
using namespace gs;

// ── numpy 辅助 ──────────────────────────────────────────────
static std::vector<double> flatten_numpy(
    py::array_t<double, py::array::c_style | py::array::forcecast> arr)
{
    auto buf = arr.request();
    auto* p = static_cast<double*>(buf.ptr);
    return {p, p + buf.size};
}

static std::vector<uint32_t> to_u32_vec(
    py::array_t<uint32_t, py::array::c_style | py::array::forcecast> arr)
{
    auto buf = arr.request();
    auto* p = static_cast<uint32_t*>(buf.ptr);
    return {p, p + buf.size};
}

PYBIND11_MODULE(graph_search_py, m) {
    m.doc() = R"doc(
        High-performance feature graph BFS/DP engine.
        Provides long-tail isolation detection and shortest distribution path
        computation on high-dimensional embedding spaces with OpenMP parallelism.
    )doc";
    m.attr("__version__") = "1.0.0";

    // ══════════════════════════════════════════════════════════
    // EdgeList 绑定
    // ══════════════════════════════════════════════════════════
    py::class_<EdgeList>(m, "EdgeList", "SoA edge list (src, dst, weight parallel arrays)")
        .def_readonly("src",    &EdgeList::src)
        .def_readonly("dst",    &EdgeList::dst)
        .def_readonly("weight", &EdgeList::weight)
        .def("__len__", &EdgeList::size);

    // ══════════════════════════════════════════════════════════
    // GraphSearch 绑定
    // ══════════════════════════════════════════════════════════
    py::class_<GraphSearch>(m, "GraphSearch", R"doc(
        High-dimensional feature graph with BFS long-tail isolation
        and DP shortest distribution path algorithms.
    )doc")
        .def(py::init<std::size_t>(), py::arg("embedding_dim") = 128)

        // ── 节点管理 ────────────────────────────────────────
        .def("add_node", &GraphSearch::add_node,
             py::arg("id"), py::arg("label_id"), py::arg("embedding"))
        .def("add_nodes_batch", &GraphSearch::add_nodes_batch,
             py::arg("ids"), py::arg("labels"), py::arg("embeddings"))
        .def("size",          &GraphSearch::size)
        .def("embedding_dim", &GraphSearch::embedding_dim)
        .def("clear",         &GraphSearch::clear)

        // ── 距离矩阵 ───────────────────────────────────────
        .def("compute_distance_matrix",
             [](GraphSearch& self) {
                 std::vector<double> mat;
                 self.compute_distance_matrix(mat);
                 const std::size_t n = self.size();
                 // 返回 numpy 2D 数组
                 py::array_t<double> result(
                     {static_cast<py::ssize_t>(n), static_cast<py::ssize_t>(n)});
                 std::copy(mat.begin(), mat.end(),
                           static_cast<double*>(result.mutable_request().ptr));
                 return result;
             },
             "Compute N x N Euclidean distance matrix (OpenMP parallel). Returns numpy 2D array.")

        // ── 图构建 ──────────────────────────────────────────
        .def("build_graph",
             [](GraphSearch& self, double threshold,
                py::array_t<double, py::array::c_style | py::array::forcecast> dist_arr) {
                 auto dist_vec = flatten_numpy(dist_arr);
                 self.build_graph(threshold, dist_vec);
             },
             py::arg("threshold"), py::arg("dist_matrix"),
             "Build undirected weighted graph from distance matrix and threshold.")

        // ── BFS 长尾孤立检测 ───────────────────────────────
        .def("bfs_longtail_isolation",
             &GraphSearch::bfs_longtail_isolation,
             py::arg("k_seeds"), py::arg("max_hops"),
             R"doc(
                 BFS long-tail isolation detection.
                 Returns list of (node_index, isolation_score) sorted descending.
             )doc")

        // ── DP 最短分布路径 ────────────────────────────────
        .def("dp_shortest_distribution_path",
             [](GraphSearch& self,
                py::array_t<uint32_t, py::array::c_style | py::array::forcecast> sources,
                std::size_t max_iter) {
                 auto src_vec = to_u32_vec(sources);
                 auto [dist, hops] = self.dp_shortest_distribution_path(src_vec, max_iter);
                 // 返回 (dist_array, hops_array)
                 py::array_t<double> dist_arr(dist.size());
                 py::array_t<int>    hops_arr(hops.size());
                 std::copy(dist.begin(), dist.end(),
                           static_cast<double*>(dist_arr.mutable_request().ptr));
                 std::copy(hops.begin(), hops.end(),
                           static_cast<int*>(hops_arr.mutable_request().ptr));
                 return py::make_tuple(dist_arr, hops_arr);
             },
             py::arg("source_indices"), py::arg("max_iterations") = 0,
             R"doc(
                 DP shortest distribution path (parallel Bellman-Ford).
                 Returns (distances_array, hops_array) as numpy arrays.
             )doc")

        // ── 导出 ────────────────────────────────────────────
        .def("top_k_isolated", &GraphSearch::top_k_isolated, py::arg("k"))
        .def("export_isolation_scores", &GraphSearch::export_isolation_scores)
        .def("adjacency", &GraphSearch::adjacency)
        .def("edges",     &GraphSearch::edges);
}
