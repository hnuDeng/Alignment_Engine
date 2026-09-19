# Label Studio 数据为中心AI工作流 - 实现指令索引

## 项目概述

本项目基于Label Studio进行二次开发，实现数据为中心AI（Data-Centric AI）工作流，包括三大核心模块：
- **Active Learning Engine**（主动学习引擎）
- **Data Quality Assessment**（数据质量评估）
- **Data Drift Detection**（数据漂移检测）

## 指令文件列表

### 阶段1：环境搭建
| 序号 | 文件名 | 内容 | 预计时间 |
|------|--------|------|----------|
| 01 | `01_project_setup.md` | 项目环境搭建、依赖安装、目录结构创建 | 1-2天 |

### 阶段2：主动学习模块
| 序号 | 文件名 | 内容 | 预计时间 |
|------|--------|------|----------|
| 02 | `02_active_learning_backend.md` | 主动学习后端架构、模型、API、序列化器 | 2-3天 |
| 03 | `03_active_learning_strategies.md` | 主动学习策略实现（不确定性、多样性、委员会等） | 2-3天 |

### 阶段3：数据质量模块
| 序号 | 文件名 | 内容 | 预计时间 |
|------|--------|------|----------|
| 04 | `04_data_quality_backend.md` | 数据质量后端架构、模型、API、序列化器 | 2-3天 |
| 05 | `05_data_quality_assessors.md` | 数据质量评估器实现（一致性、异常、偏差等） | 2-3天 |

### 阶段4：漂移检测模块
| 序号 | 文件名 | 内容 | 预计时间 |
|------|--------|------|----------|
| 06 | `06_drift_detection_backend.md` | 漂移检测后端架构、检测器、告警系统 | 2-3天 |

### 阶段5：前端实现
| 序号 | 文件名 | 内容 | 预计时间 |
|------|--------|------|----------|
| 07 | `07_frontend_implementation.md` | 前端基础架构、组件、页面实现 | 3-4天 |

### 阶段6：集成与测试
| 序号 | 文件名 | 内容 | 预计时间 |
|------|--------|------|----------|
| 08 | `08_api_integration.md` | API集成、路由配置、Django设置 | 1天 |
| 09 | `09_testing.md` | 测试用例编写、测试执行 | 2天 |

### 阶段7：文档
| 序号 | 文件名 | 内容 | 预计时间 |
|------|--------|------|----------|
| 10 | `10_documentation.md` | README、API文档、用户指南 | 1-2天 |

## 代码量统计

| 模块 | 后端代码 | 前端代码 | 测试代码 | 文档 |
|------|----------|----------|----------|------|
| Active Learning | ~5,000行 | ~3,000行 | ~2,000行 | ~1,000行 |
| Data Quality | ~5,000行 | ~3,000行 | ~2,000行 | ~1,000行 |
| Drift Detection | ~4,000行 | ~2,000行 | ~1,500行 | ~1,000行 |
| 基础设施 | ~1,000行 | ~1,000行 | - | - |
| **总计** | **~15,000行** | **~9,000行** | **~5,500行** | **~3,000行** |

**项目总代码量：约32,500行**

## 使用说明

### 如何使用这些指令

1. **按顺序执行**：按照01-10的顺序依次执行每个指令文件
2. **仔细阅读**：每个指令文件包含详细的目标、步骤和代码实现
3. **逐步验证**：每个指令文件末尾都有验证检查点，确保完成后再继续
4. **灵活调整**：根据实际情况调整实现细节

### 指令文件格式

每个指令文件包含：
- **目标**：本步骤要完成的任务
- **需要创建/修改的文件**：文件路径列表
- **详细实现**：完整的代码实现
- **验证检查点**：完成后的检查清单
- **下一步**：后续步骤指引

### 注意事项

1. **备份数据**：在开始前备份现有数据
2. **版本控制**：使用Git进行版本控制
3. **测试优先**：编写代码后立即测试
4. **文档同步**：代码变更时同步更新文档

## 技术栈

### 后端
- Python 3.9+
- Django 4.x
- Django REST Framework
- scikit-learn
- scipy
- numpy
- pandas

### 前端
- TypeScript
- React
- Recharts（图表库）
- Lucide React（图标库）
- Tailwind CSS

### 数据库
- PostgreSQL（推荐）
- SQLite（开发环境）

## 项目结构

```
label-studio/
├── active_learning/              # 主动学习模块
│   ├── strategies/              # 采样策略
│   │   ├── base.py
│   │   ├── uncertainty.py
│   │   ├── diversity.py
│   │   ├── committee.py
│   │   ├── hybrid.py
│   │   └── random.py
│   ├── selectors/               # 任务选择器
│   │   └── task_selector.py
│   ├── models.py
│   ├── api.py
│   ├── serializers.py
│   └── tests/
│
├── data_quality/                 # 数据质量模块
│   ├── assessors/               # 质量评估器
│   │   ├── base.py
│   │   ├── engine.py
│   │   ├── consistency.py
│   │   ├── agreement.py
│   │   ├── outlier.py
│   │   ├── bias.py
│   │   └── completeness.py
│   ├── reporters/               # 报告生成器
│   │   └── quality_report.py
│   ├── models.py
│   ├── api.py
│   ├── serializers.py
│   └── tests/
│
├── drift_detection/              # 漂移检测模块
│   ├── detectors/               # 漂移检测器
│   │   ├── base.py
│   │   ├── statistical.py
│   │   ├── feature_drift.py
│   │   └── label_drift.py
│   ├── alerts/                  # 告警管理
│   │   └── alert_manager.py
│   ├── models.py
│   ├── api.py
│   ├── serializers.py
│   └── tests/
│
└── web/apps/labelstudio/src/pages/DataCentricAI/
    ├── components/              # 通用组件
    │   ├── Layout.tsx
    │   ├── Navigation.tsx
    │   ├── ScoreCard.tsx
    │   └── ChartComponents.tsx
    ├── ActiveLearning/          # 主动学习页面
    ├── DataQuality/             # 数据质量页面
    ├── DriftDetection/          # 漂移检测页面
    ├── api.ts
    ├── hooks.ts
    ├── types.ts
    └── index.tsx
```

## 快速开始

### 最小化启动

如果想快速体验功能，可以只实现核心部分：

1. 执行 `01_project_setup.md` 搭建环境
2. 执行 `02_active_learning_backend.md` 创建基础模型
3. 执行 `04_data_quality_backend.md` 创建基础模型
4. 执行 `07_frontend_implementation.md` 创建前端页面
5. 执行 `08_api_integration.md` 集成路由

这样可以在1-2天内看到基本功能。

### 完整实现

如果要完整实现所有功能，建议按照顺序执行所有指令文件，预计需要2-3周时间。

## 常见问题

### Q: 如何处理数据库迁移冲突？

A: 如果遇到迁移冲突，可以：
1. 删除迁移文件重新生成
2. 使用 `python manage.py migrate --fake` 跳过冲突
3. 手动解决冲突后重新迁移

### Q: 前端依赖安装失败怎么办？

A: 尝试以下解决方案：
1. 清除缓存：`bun cache clean` 或 `npm cache clean --force`
2. 使用国内镜像：`npm config set registry https://registry.npmmirror.com`
3. 使用yarn：`yarn install`

### Q: 如何调试API？

A: 使用以下工具：
1. Django Shell：`python manage.py shell`
2. API文档：http://localhost:8000/api/docs/
3. Postman或curl测试API

## 联系方式

如有问题，请通过以下方式联系：
- 提交Issue到项目仓库
- 发送邮件至项目维护者

## 许可证

本项目基于Apache License 2.0许可证。

---

**祝您开发顺利！**
