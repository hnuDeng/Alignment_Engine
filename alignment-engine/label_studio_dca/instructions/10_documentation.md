# 指令 10：文档编写

## 目标

编写完整的项目文档，包括README、API文档、用户指南和开发者文档。

## 需要创建的文件

1. `README_DCA.md` - 项目说明文档
2. `docs/api/` - API文档目录
3. `docs/user_guide/` - 用户指南
4. `docs/developer_guide/` - 开发者指南
5. `CHANGELOG_DCA.md` - 更新日志

## 详细实现

### 10.1 项目README (`README_DCA.md`)

```markdown
# Label Studio - Data-Centric AI Workflow

基于Label Studio的数据为中心AI工作流扩展，提供智能数据管理、质量评估和漂移检测功能。

## 功能特性

### 1. 主动学习 (Active Learning)

智能选择最有价值的样本进行标注，提高标注效率。

**支持的策略：**
- 不确定性采样 (Uncertainty Sampling)
  - Least Confidence
  - Margin Sampling
  - Entropy
- 多样性采样 (Diversity Sampling)
  - 基于聚类的多样性选择
  - 基于距离的多样性选择
- 委员会查询 (Query by Committee)
  - Vote Entropy
  - KL Divergence
- 混合策略 (Hybrid Strategy)
- 随机采样 (Random Sampling) - 用于基准比较

**主要功能：**
- 自动任务选择
- 批量标注支持
- 选择分数可视化
- 轮次历史记录
- 自动训练触发

### 2. 数据质量评估 (Data Quality Assessment)

全面评估标注数据质量，发现潜在问题。

**评估维度：**
- 一致性评估 (Consistency)
  - 标注冲突检测
  - 标签一致性分析
- 标注者间一致性 (Agreement)
  - Cohen's Kappa
  - 配对一致性矩阵
- 异常检测 (Outlier Detection)
  - 标注速度异常
  - 标签分布异常
- 偏差检测 (Bias Detection)
  - 标签不平衡
  - 标注者偏好
- 完整性评估 (Completeness)
  - 任务覆盖率
  - 标注密度

**主要功能：**
- 自动质量评估
- 质量报告生成
- 问题跟踪和解决
- 标注者质量档案
- 标签统计分析

### 3. 数据漂移检测 (Data Drift Detection)

监测数据分布变化，及时发现潜在问题。

**检测类型：**
- 特征漂移 (Feature Drift)
  - Kolmogorov-Smirnov检验
  - Wasserstein距离
  - 卡方检验
- 标签漂移 (Label Drift)
  - 标签分布变化
  - 标签比例变化

**主要功能：**
- 基线管理
- 自动漂移检测
- 告警系统
- 漂移报告
- 可视化仪表盘

## 安装指南

### 环境要求

- Python 3.9+
- Node.js 18+
- PostgreSQL (推荐) 或 SQLite

### 后端安装

```bash
# 克隆仓库
git clone https://github.com/your-org/label-studio-dca.git
cd label-studio-dca

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .
pip install -r requirements_dca.txt

# 数据库迁移
python label_studio/manage.py migrate

# 创建超级用户
python label_studio/manage.py createsuperuser

# 启动后端服务器
python label_studio/manage.py runserver
```

### 前端安装

```bash
cd web

# 安装依赖
bun install  # 或 npm install

# 启动开发服务器
bun start  # 或 npm start
```

## 使用指南

### 访问Data-Centric AI

1. 登录Label Studio
2. 进入项目详情页
3. 点击左侧导航栏的 "Data-Centric AI"

### 运行质量评估

1. 进入 "Data Quality" 标签
2. 点击 "Run Assessment" 按钮
3. 等待评估完成
4. 查看评估报告和问题列表

### 配置主动学习

1. 进入 "Active Learning" 标签
2. 配置ML后端（可选）
3. 选择采样策略
4. 设置批量大小
5. 启用主动学习
6. 点击 "Select Tasks" 选择下一批任务

### 运行漂移检测

1. 进入 "Drift Detection" 标签
2. 创建基线（Baseline）
3. 选择基线
4. 点击 "Run Detection"
5. 查看漂移报告和告警

## API文档

API文档可在运行时访问：
- Swagger UI: http://localhost:8080/api/docs/
- ReDoc: http://localhost:8080/api/redoc/

### 主要API端点

#### 主动学习

- `GET /api/active-learning/configs/` - 获取配置列表
- `POST /api/active-learning/configs/` - 创建配置
- `POST /api/active-learning/configs/{id}/select/` - 选择任务
- `POST /api/active-learning/configs/{id}/toggle/` - 切换启用状态

#### 数据质量

- `POST /api/data-quality/projects/{id}/assess/` - 运行评估
- `GET /api/data-quality/projects/{id}/dashboard/` - 获取仪表盘数据
- `GET /api/data-quality/issues/` - 获取问题列表
- `POST /api/data-quality/issues/{id}/resolve/` - 解决问题

#### 漂移检测

- `POST /api/drift/baselines/` - 创建基线
- `POST /api/drift/projects/{id}/detect/` - 运行检测
- `GET /api/drift/projects/{id}/reports/` - 获取报告
- `POST /api/drift/alerts/{id}/acknowledge/` - 确认告警

## 配置说明

### Django Settings

```python
# Active Learning配置
ACTIVE_LEARNING = {
    'DEFAULT_STRATEGY': 'uncertainty',
    'DEFAULT_BATCH_SIZE': 10,
    'MAX_BATCH_SIZE': 1000,
}

# Data Quality配置
DATA_QUALITY = {
    'AUTO_ASSESS_ENABLED': False,
    'ASSESS_AFTER_COUNT': 100,
    'LOW_AGREEMENT_THRESHOLD': 0.5,
    'SPEED_ANOMALY_THRESHOLD': 3.0,
}

# Drift Detection配置
DRIFT_DETECTION = {
    'DEFAULT_THRESHOLD': 0.05,
    'CHECK_INTERVAL_HOURS': 24,
    'FEATURE_DRIFT_THRESHOLD': 0.3,
    'LABEL_DRIFT_THRESHOLD': 0.3,
}
```

## 开发指南

### 项目结构

```
label_studio/
├── active_learning/          # 主动学习模块
│   ├── strategies/          # 采样策略
│   ├── selectors/           # 任务选择器
│   └── tests/               # 测试
├── data_quality/            # 数据质量模块
│   ├── assessors/           # 质量评估器
│   ├── reporters/           # 报告生成器
│   └── tests/               # 测试
└── drift_detection/         # 漂移检测模块
    ├── detectors/           # 漂移检测器
    ├── alerts/              # 告警管理
    └── tests/               # 测试

web/apps/labelstudio/src/pages/DataCentricAI/
├── components/              # 通用组件
├── ActiveLearning/          # 主动学习页面
├── DataQuality/             # 数据质量页面
└── DriftDetection/          # 漂移检测页面
```

### 添加新策略

1. 在 `active_learning/strategies/` 创建新文件
2. 继承 `BaseStrategy` 类
3. 实现 `compute_scores` 和 `select` 方法
4. 在 `strategies/__init__.py` 注册策略
5. 编写测试

### 添加新评估器

1. 在 `data_quality/assessors/` 创建新文件
2. 继承 `BaseAssessor` 类
3. 实现 `assess` 方法
4. 在 `assessors/engine.py` 注册评估器
5. 编写测试

### 添加新检测器

1. 在 `drift_detection/detectors/` 创建新文件
2. 继承 `BaseDriftDetector` 类
3. 实现 `detect` 方法
4. 在相应的检测器中使用
5. 编写测试

## 测试

```bash
# 运行所有测试
python label_studio/manage.py test active_learning data_quality drift_detection

# 运行特定模块
python label_studio/manage.py test active_learning

# 运行并显示覆盖率
coverage run label_studio/manage.py test active_learning data_quality drift_detection
coverage report
```

## 常见问题

### Q: 如何配置ML后端？

A: 在Label Studio设置中添加ML Backend，然后在Active Learning配置中选择该后端。

### Q: 质量评估需要多长时间？

A: 取决于数据量，通常1000条数据需要1-2分钟。

### Q: 如何调整漂移检测灵敏度？

A: 在Django settings中修改 `DRIFT_DETECTION` 配置的阈值参数。

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/your-feature`)
3. 提交更改 (`git commit -m 'Add your feature'`)
4. 推送到分支 (`git push origin feature/your-feature`)
5. 创建 Pull Request

## 许可证

本项目基于Apache License 2.0许可证。

## 联系方式

- 项目主页: https://github.com/your-org/label-studio-dca
- 问题反馈: https://github.com/your-org/label-studio-dca/issues
- 邮箱: your-email@example.com
```

### 10.2 更新日志 (`CHANGELOG_DCA.md`)

```markdown
# Changelog

All notable changes to the Data-Centric AI Workflow extension will be documented in this file.

## [1.0.0] - 2026-09-18

### Added

#### Active Learning Module
- Uncertainty Sampling strategy (Least Confidence, Margin Sampling, Entropy)
- Diversity Sampling strategy (clustering-based and distance-based)
- Query by Committee strategy (Vote Entropy, KL Divergence)
- Hybrid Strategy combining multiple approaches
- Random Sampling as baseline
- Task selection with configurable batch size
- Round history tracking
- Automatic training trigger
- Feedback collection system

#### Data Quality Module
- Consistency assessment
- Inter-annotator agreement (Cohen's Kappa)
- Outlier detection (speed anomalies, distribution anomalies)
- Bias detection (label imbalance, annotator bias)
- Completeness assessment
- Quality report generation
- Issue tracking and resolution
- Annotator quality profiles
- Label quality statistics

#### Drift Detection Module
- Feature drift detection (KS Test, Chi-Square, Wasserstein)
- Label drift detection
- Baseline management
- Alert system with notifications
- Drift monitoring configuration
- Historical drift reports

#### Frontend
- Data-Centric AI main page with tab navigation
- Active Learning configuration and task selection UI
- Data Quality dashboard with charts and statistics
- Drift Detection dashboard with alerts
- Responsive design for all screen sizes

#### API
- RESTful API for all modules
- Swagger/OpenAPI documentation
- Pagination support
- Filtering and sorting

### Changed

- Updated Django settings to include new applications
- Added URL routes for new API endpoints
- Extended frontend routing for Data-Centric AI pages

### Fixed

- N/A (Initial release)

## [0.1.0] - Development

### Added

- Initial project setup
- Basic architecture design
- Database schema design
```

### 10.3 API文档模板

```markdown
# Data-Centric AI API Reference

## Base URL

```
http://localhost:8000/api
```

## Authentication

All API endpoints require authentication. Use one of the following methods:

- Session Authentication
- Token Authentication: Include `Authorization: Token <your-token>` header

## Active Learning API

### List Configurations

**Endpoint:** `GET /active-learning/configs/`

**Query Parameters:**
- `project` (integer, required): Project ID

**Response:**
```json
{
  "count": 1,
  "results": [
    {
      "id": 1,
      "project": 1,
      "project_title": "My Project",
      "strategy": "uncertainty",
      "batch_size": 10,
      "is_enabled": true,
      "round_count": 5
    }
  ]
}
```

### Create Configuration

**Endpoint:** `POST /active-learning/configs/`

**Request Body:**
```json
{
  "project": 1,
  "strategy": "uncertainty",
  "uncertainty_method": "entropy",
  "batch_size": 10,
  "is_enabled": true,
  "auto_select": false
}
```

### Select Tasks

**Endpoint:** `POST /active-learning/configs/{id}/select/`

**Request Body:**
```json
{
  "batch_size": 10
}
```

**Response:**
```json
{
  "round_id": 1,
  "round_number": 1,
  "task_ids": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "task_scores": {
    "1": 0.85,
    "2": 0.82,
    "3": 0.78
  },
  "strategy_used": "uncertainty",
  "avg_uncertainty": 0.82,
  "selection_summary": {
    "total_candidates": 100,
    "selected": 10,
    "avg_score": 0.80
  }
}
```

## Data Quality API

### Run Assessment

**Endpoint:** `POST /data-quality/projects/{project_id}/assess/`

**Request Body:**
```json
{
  "assessors": ["consistency", "agreement", "outlier"]
}
```

### Get Dashboard

**Endpoint:** `GET /data-quality/projects/{project_id}/dashboard/`

**Response:**
```json
{
  "project_id": 1,
  "overall_score": 0.85,
  "consistency_score": 0.90,
  "agreement_score": 0.80,
  "completeness_score": 0.85,
  "total_issues": 5,
  "critical_issues": 1,
  "score_trend": [0.80, 0.82, 0.85]
}
```

## Drift Detection API

### Create Baseline

**Endpoint:** `POST /drift/baselines/`

**Request Body:**
```json
{
  "project": 1,
  "name": "Initial Baseline",
  "description": "Baseline from first week of data"
}
```

### Run Detection

**Endpoint:** `POST /drift/projects/{project_id}/detect/`

**Request Body:**
```json
{
  "baseline_id": 1,
  "window_hours": 24
}
```

**Response:**
```json
{
  "id": 1,
  "drift_level": "low",
  "feature_drift_score": 0.15,
  "label_drift_score": 0.10,
  "overall_drift_score": 0.125,
  "task_count": 150
}
```

## Error Responses

All API endpoints return standard HTTP status codes:

- `200 OK`: Success
- `201 Created`: Resource created
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Permission denied
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

**Error Response Format:**
```json
{
  "error": "Error message",
  "detail": "Detailed error information"
}
```
```

## 验证检查点

- [ ] README文档完整且清晰
- [ ] 更新日志格式正确
- [ ] API文档覆盖所有端点
- [ ] 安装指南可操作
- [ ] 使用指南易于理解
- [ ] 开发者指南详细
- [ ] 代码示例正确

## 项目完成

恭喜！您已完成Label Studio数据为中心AI工作流的二次开发。

### 总结

本项目实现了：

1. **主动学习引擎** - 智能选择最有价值的样本
2. **数据质量评估** - 全面评估标注数据质量
3. **数据漂移检测** - 监测数据分布变化

### 代码统计

- 新增后端代码：约15,000行
- 新增前端代码：约8,000行
- 测试代码：约5,000行
- 文档：约3,000行
- **总计：约31,000行代码**

### 后续优化建议

1. 添加更多主动学习策略
2. 集成更先进的漂移检测算法
3. 添加实时监控功能
4. 优化大数据集性能
5. 添加更多可视化图表
6. 集成通知系统（邮件、Slack等）
7. 添加A/B测试功能
8. 支持多语言
