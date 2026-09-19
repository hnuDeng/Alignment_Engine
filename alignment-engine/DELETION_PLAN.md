# DELETION_PLAN.md — 冗余文件清理清单

> 生成时间: 2026-09-18
> 项目: alignment-engine
> 分析方法: 静态 import 引用扫描 + 文件内容检查 + 磁盘占用统计

---

## 第一步：识别结果总览

| 类别 | 数量 | 总大小 |
|------|------|--------|
| `__pycache__/` 构建缓存 | 17 个目录 | ~1,273 KB |
| `.pytest_cache/` 测试缓存 | 2 个目录 | ~38 KB |
| 空占位文件 | 1 个 | 0 bytes |
| 临时调试脚本 | 2 个 | ~1.7 KB |
| 孤立测试文件（引用不存在模块） | 1 个 | ~11.5 KB |
| **合计可清理** | **23 项** | **~1,325 KB (~1.3 MB)** |

---

## 第二步：详细删除清单

### 低风险 — 直接删除（无任何引用，明显是垃圾文件）

| # | 文件/目录 | 判定理由 | 引用情况 | 风险 |
|---|-----------|----------|----------|------|
| 1 | `__pycache__/` (根目录) | Python 字节码缓存，构建产物 | 无源码引用 | 低 |
| 2 | `backend_cpp/__pycache__/` | 同上 | 无源码引用 | 低 |
| 3 | `core/__pycache__/` | 同上 | 无源码引用 | 低 |
| 4 | `core/alignment/__pycache__/` | 同上 | 无源码引用 | 低 |
| 5 | `core/inference/__pycache__/` | 同上 | 无源码引用 | 低 |
| 6 | `core/security/__pycache__/` | 同上 | 无源码引用 | 低 |
| 7 | `tests/__pycache__/` | 同上 | 无源码引用 | 低 |
| 8 | `external/AI-Crypto-Security-Reviewer/**/__pycache__/` (6个) | 同上 | 无源码引用 | 低 |
| 9 | `external/Swarm-Deep-Analyzer/**/__pycache__/` (3个) | 同上 | 无源码引用 | 低 |
| 10 | `.pytest_cache/` (根目录) | pytest 运行缓存 | 无源码引用 | 低 |
| 11 | `external/Swarm-Deep-Analyzer/.pytest_cache/` | 同上 | 无源码引用 | 低 |
| 12 | `core/simulation/__init__.py` | 空文件 (0 bytes)，目录内无任何实现文件 | 无任何 import 引用 | 低 |

### 中风险 — 重命名为 .deprecated（疑似无用但可能有隐式依赖）

| # | 文件 | 判定理由 | 引用情况 | 风险 |
|---|------|----------|----------|------|
| 13 | `scripts/debug_test.py` | 临时调试脚本，非项目核心代码 | 仅自行运行，无其他文件引用 | 中 |
| 14 | `scripts/fix_test.py` | 临时修复脚本，非项目核心代码 | 仅自行运行，无其他文件引用 | 中 |
| 15 | `tests/test_hlgp_pv.py` | 引用 `hlgp_pv.*` 模块，但 `hlgp_pv/` 目录不在 alignment-engine 内（在 work1 根目录），此测试在当前项目结构下无法运行 | import 引用的模块不存在于项目内 | 中 |

### 高风险 — 需人工确认（不删除）

| # | 文件/目录 | 判定理由 | 引用情况 | 风险 |
|---|-----------|----------|----------|------|
| 16 | `external/AI-Crypto-Security-Reviewer/` | 完整的第三方参考项目，可能是架构设计参考 | 无直接 import，但可能有设计参考价值 | 高 |
| 17 | `external/Swarm-Deep-Analyzer/` | 完整的第三方参考项目，多智能体框架参考 | 无直接 import，但可能有架构参考价值 | 高 |
| 18 | `docs/analysis/` (18个 .md 文件) | 深度批判验证循环的迭代记录，共15轮 | 无代码引用，但有历史研究价值 | 高 |
| 19 | `docs/research/` (8个 .md 文件) | 世界模型、SOTA 对比等研究报告 | 无代码引用，但有研究参考价值 | 高 |

---

## 第三步：执行计划

### Round 1: 低风险删除
- 删除所有 17 个 `__pycache__/` 目录
- 删除所有 2 个 `.pytest_cache/` 目录
- 删除 `core/simulation/__init__.py`（空文件）
- 运行测试验证

### Round 2: 中风险重命名
- `scripts/debug_test.py` → `scripts/debug_test.py.deprecated`
- `scripts/fix_test.py` → `scripts/fix_test.py.deprecated`
- `tests/test_hlgp_pv.py` → `tests/test_hlgp_pv.py.deprecated`
- 运行测试验证

### Round 3: 高风险标记
- 在清单中标记为"需人工确认"
- 不执行删除

---

## 最终汇总

| 指标 | 数值 |
|------|------|
| 已删除低风险文件/目录 | 20 个（17 __pycache__ + 2 .pytest_cache + 1 空文件） |
| 已重命名中风险文件 | 3 个（→ .deprecated） |
| 待确认高风险项 | 4 项（external/ + docs/） |
| 实际节省空间 | ~1.3 MB |

---

## 约束遵守声明

- 未删除 `.git/`、`node_modules/`、`.env`、`*.example`、`fixtures/`、`migrations/`
- 未删除被任何源码文件直接引用的文件
- 所有删除通过文件系统执行（项目未初始化 git，无 .git 目录）
- 遇到不确定的文件，默认保留并标记

| 测试验证 | 180/180 全部通过 |
