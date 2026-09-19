cmake_minimum_required(VERSION 3.14)
project(graph_search_engine
    VERSION 2.0.0
    LANGUAGES CXX
    DESCRIPTION "High-performance SIMD-aligned graph computation engine for feature space analytics"
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# -- OpenMP ----------------------------------------------------------------
find_package(OpenMP REQUIRED)

# -- SIMD / Optimization flags --------------------------------------------
if(MSVC)
    add_compile_options(/O2 /Oi /GL /arch:AVX2 /fp:fast /openmp)
    add_link_options(/LTCG)
else()
    add_compile_options(-O3 -mavx2 -mfma -ffast-math -funroll-loops)
endif()

# ==========================================================================
# Core static library #1: Original GraphSearch (backward compatibility)
# ==========================================================================
add_library(graph_search STATIC
    src/graph_search.cpp
)

target_include_directories(graph_search PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_compile_features(graph_search PUBLIC cxx_std_17)
target_link_libraries(graph_search PUBLIC OpenMP::OpenMP_CXX)

# ==========================================================================
# Core static library #2: SIMD-aligned memory pool
# ==========================================================================
add_library(memory_pool STATIC
    src/memory_pool.cpp
)

target_include_directories(memory_pool PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_compile_features(memory_pool PUBLIC cxx_std_17)

# ==========================================================================
# Core static library #3: Graph algorithms (BFS + Dijkstra + Lock-free queue)
# ==========================================================================
add_library(graph_algorithms STATIC
    src/graph_algorithms.cpp
)

target_include_directories(graph_algorithms PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_compile_features(graph_algorithms PUBLIC cxx_std_17)
target_link_libraries(graph_algorithms
    PUBLIC
        memory_pool
        OpenMP::OpenMP_CXX
)

# ==========================================================================
# pybind11 (FetchContent)
# ==========================================================================
include(FetchContent)
FetchContent_Declare(pybind11
    GIT_REPOSITORY https://github.com/pybind/pybind11.git
    GIT_TAG        v2.12.0
)
FetchContent_MakeAvailable(pybind11)

# ==========================================================================
# Python module #1: Original graph_search_py (backward compatibility)
# ==========================================================================
pybind11_add_module(graph_search_py src/pybind_wrapper.cpp)
target_link_libraries(graph_search_py PRIVATE graph_search)
set_target_properties(graph_search_py PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
)

# ==========================================================================
# Python module #2: graph_engine_py
#   - MemoryPool + GraphEngine + BFS/Dijkstra
#   - Exception translation (C++ -> Python custom exceptions)
#   - GIL release during compute-intensive operations
# ==========================================================================
pybind11_add_module(graph_engine_py src/pybind_adapter.cpp)
target_link_libraries(graph_engine_py
    PRIVATE
        graph_algorithms
        memory_pool
)
target_include_directories(graph_engine_py PRIVATE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
set_target_properties(graph_engine_py PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
)

# ==========================================================================
# C++ unit tests (optional, enable with -DBUILD_TESTING=ON)
# ==========================================================================
if(BUILD_TESTING)
    enable_testing()
    add_executable(test_memory_pool tests/test_memory_pool.cpp)
    target_link_libraries(test_memory_pool PRIVATE memory_pool)
    add_test(NAME memory_pool_test COMMAND test_memory_pool)

    add_executable(test_graph_algorithms tests/test_graph_algorithms.cpp)
    target_link_libraries(test_graph_algorithms PRIVATE graph_algorithms memory_pool)
    add_test(NAME graph_algorithms_test COMMAND test_graph_algorithms)
endif()

# ==========================================================================
# Install
# ==========================================================================
install(TARGETS graph_search memory_pool graph_algorithms
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)
install(DIRECTORY include/ DESTINATION include)
