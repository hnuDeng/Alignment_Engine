# Multi-Agent Visual Analytics Engine — 项目完整状态文档

> **生成时间**: 2026-09-18  
> **工作目录**: `E:\codex Project\work1`  
> **环境**: Python 3.11.9 | Node.js 已安装 | 无 GPU | 无 FiftyOne | Windows PowerShell  
> **测试状态**: 188 Python tests PASSED | 84 Jest tests PASSED | `tsc --noEmit` 0 errors  
> **前端覆盖率**: Statements 98.66% | Branches 99.08% | Functions 100% | Lines 99.31%

---

## 目录

1. [项目总体架构](#1-项目总体架构)
2. [完整文件结构](#2-完整文件结构)
3. [任务 1: Python Pipeline Core](#3-任务-1-python-pipeline-core)
4. [任务 2: C++ Feature Graph Engine](#4-任务-2-c-feature-graph-engine)
5. [任务 3: Inference Scheduler](#5-任务-3-inference-scheduler)
6. [任务 4.1: WebGL Engine](#6-任务-41-webgl-engine)
7. [任务 4.2: Store Layer](#7-任务-42-store-layer)
8. [任务 4.3: UI Component Library](#8-任务-43-ui-component-library)
9. [任务 4.4: Frontend Test Framework](#9-任务-44-frontend-test-framework)
10. [安全审计模块](#10-安全审计模块)
11. [待完成工作](#11-待完成工作)
12. [关键运行命令](#12-关键运行命令)

---

## 1. 项目总体架构

```
Extractor (感知) → Analyzer (推理) → Reviewer (审计执行)
     ↓                   ↓                   ↓
 DataSliceContext    DriftReport        ReviewDecision
  (Pydantic)         (Pydantic)          (Pydantic)
```

核心设计原则：
- **强类型流水线**: 线性流转，节点间通过 Pydantic 不可变数据类传递
- **AST 代码审计**: 利用 Python `ast` 模块拦截高危调用
- **完美降级**: 无 FiftyOne/CUDA 环境自动回退到 Mock/NumPy

---

## 2. 完整文件结构

```
E:\codex Project\work1\
├── schemas.py                          # Pydantic 数据契约层
├── main.py                             # 流水线编排器
├── pytest.ini                          # pytest 配置
│
├── core/
│   ├── __init__.py
│   ├── extractor.py                    # 感知模块 (FiftyOne/Mock)
│   ├── analyzer.py                     # 推理模块 (CUDA/NumPy)
│   ├── reviewer.py                     # 审计+执行模块
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── memory_manager.py           # 显存状态机 + VRAM 监控
│   │   ├── model_loader.py             # 4-bit 量化 + FP16 模型加载
│   │   └── batch_engine.py             # 异步队列批处理引擎
│   └── security/
│       ├── __init__.py
│       ├── ast_taint_analyzer.py       # AST 污点分析器
│       └── sandbox_manager.py          # 沙盒执行管理器
│
├── backend_cpp/
│   ├── CMakeLists.txt                  # CMake 构建文件
│   ├── python_bridge.py                # Python 桥接层
│   ├── include/
│   │   ├── graph_search.h              # 图搜索头文件
│   │   ├── feature_graph.h             # 特征图数据结构
│   │   └── drift_detector.h            # 漂移检测器
│   ├── src/
│   │   ├── graph_search.cpp            # BFS + 动态规划实现
│   │   ├── feature_graph.cpp           # 高维特征无向图
│   │   ├── drift_detector.cpp          # 漂移检测算法
│   │   └── pybind_wrapper.cpp          # pybind11 绑定
│   ├── bindings/
│   │   └── py_bindings.cpp             # 备用绑定入口
│   └── tests/
│       └── test_feature_graph.cpp      # C++ 单元测试
│
├── tests/
│   ├── __init__.py
│   ├── test_schemas.py                 # 16 tests
│   ├── test_extractor.py               # 16 tests
│   ├── test_analyzer.py                # 16 tests
│   ├── test_reviewer.py                # 49 tests
│   ├── test_pipeline.py                # 7 tests
│   ├── test_inference.py               # 25 tests
│   ├── test_cpp_bridge.py              # 15 tests
│   ├── test_cpp_graph_search.py        # 8 tests
│   └── test_security.py                # 36 tests
│
├── frontend_plugin/
│   ├── jest.config.js                  # Jest 配置
│   ├── tsconfig.json                   # TypeScript 配置
│   ├── package.json
│   ├── src/
│   │   ├── types/
│   │   │   └── index.ts                # 基础类型系统
│   │   ├── store/
│   │   │   ├── types.ts                # 8 pipeline 枚举, 9 接口
│   │   │   ├── agentSlice.ts           # 56 判别联合 action 类型
│   │   │   ├── datasetSlice.ts         # 21 action 类型
│   │   │   ├── DataNormalizer.ts       # 数据标准化工具
│   │   │   ├── socketMiddleware.ts     # WebSocket 中间件
│   │   │   └── index.ts                # Barrel 导出
│   │   ├── webgl_engine/
│   │   │   ├── vertex_shader.glsl      # Billboard 顶点着色器
│   │   │   ├── fragment_shader.glsl    # SDF + glow 片段着色器
│   │   │   ├── BufferGeometryManager.ts # SoA Float32 布局, 64B 对齐
│   │   │   ├── OrbitController.ts      # 正交相机, 缩放/平移/惯性
│   │   │   ├── Raycaster.ts            # 八叉树空间索引, KNN
│   │   │   └── glsl.d.ts               # GLSL 类型声明
│   │   ├── components/
│   │   │   ├── DriftScatterPlot.tsx    # WebGL2 散点图 (原生 GL)
│   │   │   ├── ui/
│   │   │   │   ├── theme.ts            # 30+ CSS 自定义属性
│   │   │   │   ├── VirtualTable.tsx     # 虚拟滚动表格
│   │   │   │   ├── DriftTimeline.tsx   # 漂移时间线
│   │   │   │   ├── SandboxLogViewer.tsx # Python 语法高亮日志
│   │   │   │   └── CommandPalette.tsx   # 模糊搜索命令面板
│   │   │   ├── AgentCopilotPanel.tsx
│   │   │   ├── DriftAlert.tsx
│   │   │   └── ReviewerPanel.tsx       # 审计面板
│   │   ├── hooks/
│   │   │   └── useDriftStream.ts       # 漂移数据流 hook
│   │   └── utils/
│   │       └── websocket.ts            # WebSocket 客户端
│   └── tests/
│       ├── jest.config.js
│       ├── __mocks__/
│       │   ├── fileMock.js
│       │   └── fiftyoneMock.js
│       ├── mocks/
│       │   └── WebGLCanvas.mock.ts     # ~470 行, 完整 GL2 Mock
│       ├── store/
│       │   └── agentSlice.test.ts      # 64 test cases, 12 describe blocks
│       └── components/
│           └── ReviewerPanel.test.tsx   # 20 test cases, 10 维度
│
├── dca-project/                        # 参考项目 (未修改)
├── dca-instructions/                   # 参考文档 (未修改)
├── AI-Crypto-Security-Reviewer/        # 独立子项目 (未修改)
├── Swarm-Deep-Analyzer/                # 独立子项目 (未修改)
│
└── *.md                                # 深度批判/循环思考文档
```

---

## 3. 任务 1: Python Pipeline Core

### schemas.py — 数据契约层

| 数据类 | 字段 | 说明 |
|--------|------|------|
| `DataSliceContext` | `samples: List[SampleRecord]`, `source: str`, `slice_id: str` | 感知模块输出, 包含图像特征和元数据 |
| `SampleRecord` | `image_id: str`, `label: str`, `confidence: float`, `embedding: List[float]` | 单个样本记录 |
| `DriftReport` | `anomalous_ids: List[str]`, `reasons: Dict[str, str]`, `drift_score: float` | 漂移分析报告 |
| `ReviewDecision` | `script: str`, `ast_passed: bool`, `ast_violations: List[str]`, `executed: bool` | 审计决策结果 |

### core/extractor.py — 感知模块

- **正常路径**: 连接 FiftyOne Session, 获取长尾样本
- **降级路径**: `uuid` 随机生成 10 条数据, 128 维 embedding, NumPy 随机分布
- **测试**: 16 tests (标签分布, 维度一致性, 边界条件)

### core/analyzer.py — 推理模块

- **正常路径**: PyTorch 视觉模型, `torch.cuda.empty_cache()`, 半精度推理
- **降级路径**: 欧氏距离 + 均值偏移, 挑出 2-3 个异常样本
- **测试**: 16 tests (漂移检测, 分数范围, 异常数量)

### core/reviewer.py — 审计+执行模块

- `generate_script(report)`: 生成 FiftyOne Python 脚本
- `ast_static_check(script)`: 拦截 `__import__`, `exec`, `eval`, `os`, `subprocess`, `sys`
- `execute(script)`: AST 通过后执行, Mock 环境仅打印日志
- **测试**: 49 tests (脚本生成, AST 拦截, 执行降级)

### main.py — 流水线编排

- 严格 Extractor → Analyzer → Reviewer 线性流转
- `logging` 配置 INFO 级别
- **测试**: 7 tests (端到端流水线, 日志输出, 数据流转)

---

## 4. 任务 2: C++ Feature Graph Engine

### 核心算法

| 文件 | 功能 |
|------|------|
| `include/feature_graph.h` | 高维特征无向图, `FeatureNode` 结构体 (128维向量, 邻接表) |
| `include/graph_search.h` | BFS 遍历, 最短分布路径 (Dijkstra 变体), 长尾孤立节点检测 |
| `include/drift_detector.h` | 基于距离阈值的漂移检测 |
| `src/graph_search.cpp` | BFS + 动态规划完整实现, OpenMP 并行化 |
| `src/feature_graph.cpp` | 图构建, 边添加, 节点查询 |
| `src/drift_detector.cpp` | 批量漂移计算, 阈值过滤 |

### 内存与并发

- OpenMP `#pragma omp parallel for` 多线程并发
- 64 字节内存对齐 (`alignas(64)`)
- 无锁读取, 临界区写入保护

### Python 绑定

- `pybind_wrapper.cpp`: 暴露 `FeatureGraph` 类, `add_node`, `bfs`, `find_isolated_nodes`, `shortest_path`
- `python_bridge.py`: Python 端桥接, 含 Mock 降级 (纯 Python dict 图)
- **测试**: 15 + 8 tests (C++ 桥接, 图搜索算法)

---

## 5. 任务 3: Inference Scheduler

### core/inference/memory_manager.py — 显存状态机

```python
class MemoryManager:
    """监控 WSL2 下 GPU 显存占用, VRAM >= 90% 触发紧急卸载"""
    - get_gpu_memory() -> tuple[used, total]  # nvidia-smi 或 pynvml
    - check_pressure() -> bool                # 阈值 90%
    - emergency_offload(tensors) -> None       # GPU → CPU 张量迁移
    - Mock 降级: 返回固定值 (2048MB used, 8192MB total)
```

### core/inference/model_loader.py — 模型加载优化

```python
class ModelLoader:
    """4-bit 量化 (BitsAndBytes) + FP16 混合精度"""
    - load_with_quantization(model_name)       # load_in_4bit=True
    - prepare_fp16_inference(model)             # model.half()
    - Mock 降级: 返回 MagicMock 模拟模型对象
```

### core/inference/batch_engine.py — 异步批处理引擎

```python
class BatchEngine:
    """基于异步队列的批处理, 收集→打包→GPU计算→清理"""
    - __init__(max_batch_size, max_wait_ms)
    - submit(slice: DataSliceContext) -> Future
    - _process_batch(batch)                    # GPU 推理
    - cleanup()                                # torch.cuda.empty_cache() + gc.collect()
    - Mock 降级: NumPy 矩阵乘法模拟
```

- **测试**: 25 tests (显存监控, 模型加载, 批处理, 降级路径)

---

## 6. 任务 4.1: WebGL Engine

### 原生 WebGL2 实现 (零 Three.js 依赖)

| 文件 | 行数 | 核心能力 |
|------|------|----------|
| `vertex_shader.glsl` | ~70 | Instanced Billboard, 脉冲动画, 发光效果 |
| `fragment_shader.glsl` | ~90 | SDF 圆形 + glow 衰减 + 选中环 + 深度雾 |
| `BufferGeometryManager.ts` | ~364 | SoA Float32Array 布局, 64B 对齐, 脏范围增量上传, `embeddingToRGB()` 128维→RGB |
| `OrbitController.ts` | ~356 | 正交相机, 鼠标缩放/平移+惯性, `screenToWorld`/`worldToScreen`, `panTo()` smoothstep |
| `Raycaster.ts` | ~398 | 八叉树空间索引, KNN max-heap 剪枝, 半径查询, AABB 框选 |

`DriftScatterPlot.tsx` 直接使用这些原语渲染, 不经过 Three.js.

---

## 7. 任务 4.2: Store Layer

### 状态管理 (无 Redux 依赖, 使用 React useReducer)

| 文件 | 行数 | 核心能力 |
|------|------|----------|
| `types.ts` | ~230 | 8 pipeline 枚举, 9 接口 (AgentState, DriftReport, ReviewLog 等) |
| `agentSlice.ts` | ~500 | **56 判别联合 action** (Extractor/Analyzer/Reviewer 生命周期, 连接, 漂移, UMAP, 选择, 流式, 管道, 批次, 系统) |
| `datasetSlice.ts` | ~200 | **21 action** (数据集管理, 过滤, 高亮, 框选, 统计) |
| `DataNormalizer.ts` | ~280 | `mergeReport`, `mergeSamples`, `removeReport`, `enrichWithUmap`, `computeStats`, `batchMerge` |
| `socketMiddleware.ts` | ~330 | 指数退避重连, 心跳, 有界队列(256), JSON 序列化, action↔message 双向映射 |

---

## 8. 任务 4.3: UI Component Library

### 零外部 UI 依赖, 47 个 ARIA 属性

| 文件 | 行数 | 核心能力 |
|------|------|----------|
| `theme.ts` | ~280 | 30+ CSS 自定义属性 (`--ac-*`), 暗色/亮色切换, FiftyOne 暗色调色板 |
| `VirtualTable.tsx` | ~370 | 虚拟滚动(overscan buffer), 列排序, 拖拽列宽, 键盘导航, `aria-grid` |
| `DriftTimeline.tsx` | ~280 | 严重度编码标记, 滚轮缩放+拖拽平移, 交替放置, tooltip, `aria-list` |
| `SandboxLogViewer.tsx` | ~330 | Python 语法高亮(关键字/字符串/注释), 折叠, 搜索高亮, 行复制, `aria-log` |
| `CommandPalette.tsx` | ~420 | 模糊匹配评分, Cmd+K 切换, 最近命令(localStorage), 分类分组, `aria-combobox` |

---

## 9. 任务 4.4: Frontend Test Framework

### 覆盖率报告

```
Statements   : 98.66% ( 148/150 )
Branches     : 99.08% ( 108/109 )
Functions    : 100% ( 24/24 )
Lines        : 99.31% ( 144/145 )
```

### 测试文件

| 文件 | 测试数 | 核心覆盖 |
|------|--------|----------|
| `agentSlice.test.ts` | 64 tests, 12 describe blocks | 全部 56 action 类型 + 复合场景 + 边界条件 |
| `ReviewerPanel.test.tsx` | 20 tests, 10 维度 | 空状态, AST pass/fail, sandbox pass/fail, accepted/rejected, 脚本展开, accept/reject 流程 |
| `WebGLCanvas.mock.ts` | ~470 行基础设施 | `MockWebGL2Context`: 60+ GL 方法, shader/program/buffer/VAO/texture 池, draw call 记录, uniform 跟踪, 状态机, 错误注入, `createMockCanvas()` 工厂, `installRafMock()` |

---

## 10. 安全审计模块

### core/security/ast_taint_analyzer.py

- AST 遍历检测危险模式: `eval()`, `exec()`, `__import__()`, `os.system()`, `subprocess.call()`
- 变量追踪: 检测从用户输入到危险调用的数据流
- **测试**: 含在 test_security.py 中 (36 tests)

### core/security/sandbox_manager.py

- 优先使用 Docker 沙盒执行
- 降级: 子进程 `subprocess.run()` + 超时 + 环境变量隔离
- Mock: 直接打印执行日志

---

## 11. 待完成工作

| 编号 | 任务 | 优先级 | 说明 |
|------|------|--------|------|
| 1 | 集成测试 (Python → WebSocket → React) | 高 | `SocketMiddleware` 和 `useDriftStream` 已存在但未通过集成测试连接 |
| 2 | WebGL 引擎单元测试 | 中 | `BufferGeometryManager`, `OrbitController`, `Octree` 缺少直接单元测试 (Mock 基础设施已就绪) |
| 3 | 端到端管道测试 | 中 | `main.py` → WebSocket → 前端接收的完整链路 |
| 4 | 清理临时文件 | 低 | `tests/__mocks__/_fix.py` 一次性辅助文件待删除 |

---

## 12. 关键运行命令

```powershell
# Python 测试 (188 tests)
cd "E:\codex Project\work1"
python -m pytest tests/ --tb=short -q

# TypeScript 类型检查
cd "E:\codex Project\work1\frontend_plugin"
npx tsc --noEmit

# 前端测试 (84 tests)
cd "E:\codex Project\work1\frontend_plugin"
npx jest --config jest.config.js

# 前端覆盖率报告
cd "E:\codex Project\work1\frontend_plugin"
npx jest --config jest.config.js --coverage

# 运行完整流水线
cd "E:\codex Project\work1"
python main.py
```

---

## 新窗口启动指令

在新窗口中使用以下 prompt 启动:

```
请阅读 E:\codex Project\work1\PROJECT_STATUS.md 了解项目完整状态。
本项目是基于 FiftyOne 的"多智能体可视分析引擎",已完成 Task 1-3 (Python Pipeline + C++ Engine + Inference Scheduler) 和 Task 4.1-4.4 (WebGL Engine + Store + UI + Tests)。

当前测试状态: 188 Python + 84 Jest 全部通过, 覆盖率 >98%。

待完成工作:
1. 集成测试 (Python Pipeline → WebSocket → React Plugin 端到端)
2. WebGL 引擎原语单元测试 (BufferGeometryManager, OrbitController, Octree)
3. 清理临时文件 tests/__mocks__/_fix.py

请从以上待办项中继续工作。
```

---

## 环境约束备忘

| 约束 | 影响 | 当前处理 |
|------|------|----------|
| 无 GPU/CUDA | torch.cuda 调用失败 | NumPy 降级 + MagicMock |
| 无 FiftyOne | 数据集操作失败 | uuid + numpy 随机数据 |
| 无 Docker | 沙盒无法隔离 | subprocess + 超时降级 |
| Windows PowerShell | 路径/命令差异 | 所有命令已适配 PS 语法 |
| `@fiftyone/plugins` 不在 npm | 前端 peerDep | 标记 optional + mock |
