# Label Studio - Data-Centric AI Workflow (DCAIA)

基于Label Studio的数据为中心AI工作流二次开发项目

## 项目概述

本项目在Label Studio基础上实现数据为中心AI（Data-Centric AI）工作流，包含三大核心模块：

- **Active Learning Engine** - 主动学习引擎，智能选择最有价值的样本
- **Data Quality Assessment** - 数据质量评估，全面检测标注质量问题
- **Data Drift Detection** - 数据漂移检测，监测数据分布变化

## 目录结构

```
label-studio-dcaia/
├── instructions/              # 实现指令（按顺序执行）
│   ├── README.md             # 指令概述
│   ├── INDEX.md              # 完整索引和快速开始
│   ├── 01_project_setup.md   # 环境搭建
│   ├── 02_active_learning_backend.md
│   ├── 03_active_learning_strategies.md
│   ├── 04_data_quality_backend.md
│   ├── 05_data_quality_assessors.md
│   ├── 06_drift_detection_backend.md
│   ├── 07_frontend_implementation.md
│   ├── 08_api_integration.md
│   ├── 09_testing.md
│   ├── 10_documentation.md
│   └── legacy/               # 早期版本指令（参考用）
│
├── implementation/            # 实现代码
│   ├── backend/              # 后端Python代码
│   │   ├── active_learning/  # 主动学习模块
│   │   ├── data_quality/     # 数据质量模块
│   │   └── drift_detection/  # 漂移检测模块
│   ├── frontend/             # 前端TypeScript代码
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   └── types/
│   ├── tests/                # 测试代码
│   └── requirements.txt      # Python依赖
│
├── docs/                      # 项目文档
│
└── CHANGELOG.md               # 更新日志
```

## 快速开始

### 1. 环境准备

```bash
# 克隆Label Studio
git clone https://github.com/HumanSignal/label-studio.git
cd label-studio

# 按照 instructions/01_project_setup.md 搭建环境
```

### 2. 按指令实现

按照 `instructions/` 目录中的指令文件顺序执行：

1. `01_project_setup.md` - 环境搭建
2. `02_active_learning_backend.md` - 主动学习后端
3. `03_active_learning_strategies.md` - 主动学习策略
4. `04_data_quality_backend.md` - 数据质量后端
5. `05_data_quality_assessors.md` - 数据质量评估器
6. `06_drift_detection_backend.md` - 漂移检测后端
7. `07_frontend_implementation.md` - 前端实现
8. `08_api_integration.md` - API集成
9. `09_testing.md` - 测试
10. `10_documentation.md` - 文档

### 3. 使用实现代码

`implementation/` 目录包含已完成的代码实现，可直接参考或使用。

## 代码统计

| 模块 | 后端代码 | 前端代码 | 测试代码 |
|------|----------|----------|----------|
| Active Learning | ~5,000行 | ~3,000行 | ~2,000行 |
| Data Quality | ~5,000行 | ~3,000行 | ~2,000行 |
| Drift Detection | ~4,000行 | ~2,000行 | ~1,500行 |
| **总计** | **~14,000行** | **~8,000行** | **~5,500行** |

**项目总代码量：约27,500行**

## 技术栈

- **后端**: Python 3.9+, Django, Django REST Framework, scikit-learn, scipy
- **前端**: TypeScript, React, Recharts, Lucide React
- **数据库**: PostgreSQL / SQLite

## 许可证

基于Apache License 2.0
