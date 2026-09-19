/**
 * @file  py_bindings.cpp
 * @brief pybind11 绑定层 —— 将 C++ FeatureGraph 和 DriftDetector 暴露给 Python
 *
 * Python 端用法示例：
 *   import feature_graph_py as fgp
 *   detector = fgp.DriftDetector(embedding_dim=128, sigma=2.0, max_outliers=3)
 *   result   = detector.detect(ids, labels, flat_embeddings)
 *   print(result.outlier_ids)
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>            // 自动转换 vector / pair / string
#include <pybind11/numpy.h>          // numpy 数组桥接

#include "drift_detector.h"
#include "feature_graph.h"

namespace py = pybind11;

// ── 辅助：将 numpy 2D 数组转为扁平 vector ───────────────────
static std::vector<double> numpy_to_flat_vec(py::array_t<double, py::array::c_style | py::array::forcecast> arr) {
    auto buf = arr.request();
    if (buf.ndim == 1) {
        // 已经是扁平的
        auto* ptr = static_cast<double*>(buf.ptr);
        return {ptr, ptr + buf.shape[0]};
    }
    if (buf.ndim == 2) {
        auto* ptr = static_cast<double*>(buf.ptr);
        return {ptr, ptr + buf.shape[0] * buf.shape[1]};
    }
    throw std::invalid_argument("expected 1D or 2D numpy array");
}

// ── 辅助：将 numpy 1D uint32 数组转为 vector ───────────────
static std::vector<uint32_t> numpy_to_uint32_vec(py::array_t<uint32_t, py::array::c_style | py::array::forcecast> arr) {
    auto buf = arr.request();
    auto* ptr = static_cast<uint32_t*>(buf.ptr);
    return {ptr, ptr + buf.shape[0]};
}

PYBIND11_MODULE(feature_graph_py, m) {
    m.doc() = R"doc(
        High-performance feature graph computation engine.
        
        Provides BFS-based anomaly detection on high-dimensional embedding spaces
        with OpenMP parallelization and 64-byte memory alignment.
    )doc";

    // ══════════════════════════════════════════════════════════
    // DriftResult 绑定
    // ══════════════════════════════════════════════════════════
    py::class_<fg::DriftResult>(m, "DriftResult", R"doc(
        Result of a drift detection pass.
        
        Attributes:
            outlier_ids:      List of anomalous sample IDs.
            outlier_scores:   Corresponding BFS isolation scores.
            outlier_reasons:  Human-readable drift reason strings.
            mean_distance:    Mean Euclidean distance to centroid.
            threshold:        Drift threshold (mean + sigma * std).
    )doc")
        .def_readonly("outlier_ids",      &fg::DriftResult::outlier_ids)
        .def_readonly("outlier_scores",   &fg::DriftResult::outlier_scores)
        .def_readonly("outlier_reasons",  &fg::DriftResult::outlier_reasons)
        .def_readonly("mean_distance",    &fg::DriftResult::mean_distance)
        .def_readonly("threshold",        &fg::DriftResult::threshold)
        .def("__repr__", [](const fg::DriftResult& r) {
            return "<DriftResult outliers=" +
                   std::to_string(r.outlier_ids.size()) +
                   " mean_dist=" + std::to_string(r.mean_distance) +
                   " threshold=" + std::to_string(r.threshold) + ">";
        });

    // ══════════════════════════════════════════════════════════
    // FeatureGraph<double> 绑定（调试 / 高级用法）
    // ══════════════════════════════════════════════════════════
    py::class_<fg::FeatureGraph<double>>(m, "FeatureGraph", R"doc(
        High-dimensional feature graph with BFS-based anomaly detection.
        
        Manages a collection of FeatureNodes and provides:
        - Centroid distance computation (OpenMP parallel)
        - Adjacency graph construction (threshold-based)
        - BFS isolation scoring
    )doc")
        .def(py::init<std::size_t>(), py::arg("embedding_dim") = 128)
        .def("add_node", &fg::FeatureGraph<double>::add_node,
             py::arg("id"), py::arg("label_id"), py::arg("embedding"),
             "Add a single node with its embedding vector.")
        .def("compute_centroid_distances",
             &fg::FeatureGraph<double>::compute_centroid_distances,
             "Compute Euclidean distance from each node to the centroid (parallel).")
        .def("build_adjacency_graph",
             &fg::FeatureGraph<double>::build_adjacency_graph,
             py::arg("threshold"),
             "Build adjacency graph: connect nodes within threshold distance.")
        .def("bfs_isolation_score",
             &fg::FeatureGraph<double>::bfs_isolation_score,
             py::arg("k_nearest"), py::arg("max_hops"),
             "Run BFS from k nearest-to-centroid nodes, return isolation scores.")
        .def("top_outliers", &fg::FeatureGraph<double>::top_outliers,
             py::arg("top_n"),
             "Return indices of top_n most distant nodes from centroid.")
        .def("export_isolation_results",
             &fg::FeatureGraph<double>::export_isolation_results,
             "Export (ids, scores) pairs for all nodes.")
        .def("size", &fg::FeatureGraph<double>::size)
        .def("embedding_dim", &fg::FeatureGraph<double>::embedding_dim)
        .def("clear", &fg::FeatureGraph<double>::clear);

    // ══════════════════════════════════════════════════════════
    // DriftDetector 绑定（主入口）
    // ══════════════════════════════════════════════════════════
    py::class_<fg::DriftDetector>(m, "DriftDetector", R"doc(
        High-level drift detector combining FeatureGraph + BFS anomaly scoring.

        Usage:
            detector = DriftDetector(embedding_dim=128, sigma=2.0)
            result = detector.detect(ids, labels, embeddings_flat)
    )doc")
        .def(py::init<std::size_t, double, std::size_t, std::size_t, std::size_t, double>(),
             py::arg("embedding_dim")       = 128,
             py::arg("sigma")               = 2.0,
             py::arg("max_outliers")        = 3,
             py::arg("k_nearest")           = 5,
             py::arg("max_bfs_hops")        = 10,
             py::arg("adjacency_threshold") = 15.0,
             R"doc(
                 Construct a DriftDetector.

                 Args:
                     embedding_dim:       Embedding vector dimension (default 128).
                     sigma:               Threshold multiplier (mean + sigma * std).
                     max_outliers:        Max number of outliers to report.
                     k_nearest:           Number of BFS seed nodes.
                     max_bfs_hops:        Maximum BFS traversal depth.
                     adjacency_threshold: Euclidean distance threshold for adjacency.
             )doc")
        .def("detect",
             [](fg::DriftDetector& self,
                py::array_t<uint32_t, py::array::c_style | py::array::forcecast> ids_arr,
                py::array_t<uint32_t, py::array::c_style | py::array::forcecast> labels_arr,
                py::array_t<double,   py::array::c_style | py::array::forcecast> emb_arr)
             {
                 auto ids_vec    = numpy_to_uint32_vec(ids_arr);
                 auto labels_vec = numpy_to_uint32_vec(labels_arr);
                 auto emb_vec    = numpy_to_flat_vec(emb_arr);
                 return self.detect(ids_vec, labels_vec, emb_vec);
             },
             py::arg("ids"),
             py::arg("labels"),
             py::arg("embeddings"),
             R"doc(
                 Run drift detection on the given samples.

                 Args:
                     ids:         1D numpy array of uint32 sample IDs.
                     labels:      1D numpy array of uint32 label IDs.
                     embeddings:  2D numpy array (N x D) of float64 embeddings,
                                  or 1D flattened array of length N*D.

                 Returns:
                     DriftResult with outlier IDs, scores, and reasons.
             )doc");

    // ══════════════════════════════════════════════════════════
    // 模块级版本信息
    // ══════════════════════════════════════════════════════════
    m.attr("__version__") = "1.0.0";
#ifdef FEATURE_GRAPH_USE_OPENMP
    m.attr("openmp_enabled") = true;
#else
    m.attr("openmp_enabled") = false;
#endif
}
