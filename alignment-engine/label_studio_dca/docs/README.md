# Data-Centric AI Workflow

基于Label Studio理念的数据为中心AI工作流实现，提供智能数据管理、质量评估和漂移检测功能。

## 功能特性

### 1. 主动学习 (Active Learning)

智能选择最有价值的样本进行标注。

**支持的策略：**
- 不确定性采样 (Uncertainty Sampling)
  - Least Confidence
  - Margin Sampling
  - Entropy
- 多样性采样 (Diversity Sampling)
- 委员会查询 (Query by Committee)
- 混合策略 (Hybrid Strategy)
- 随机采样 (Random Sampling) - 基准比较

### 2. 数据质量评估 (Data Quality Assessment)

全面评估标注数据质量。

**评估维度：**
- 一致性评估 (Consistency)
- 标注者间一致性 (Agreement)
- 异常检测 (Outlier Detection)
- 偏差检测 (Bias Detection)
- 完整性评估 (Completeness)

### 3. 数据漂移检测 (Data Drift Detection)

监测数据分布变化。

**检测类型：**
- 特征漂移 (Feature Drift)
- 标签漂移 (Label Drift)

## 项目结构

```
dca-project/
├── backend/                    # 后端Python代码
│   ├── active_learning/       # 主动学习模块
│   ├── data_quality/          # 数据质量模块
│   ├── drift_detection/       # 漂移检测模块
│   └── utils/                 # 工具函数
├── frontend/                  # 前端TypeScript代码
│   ├── api/                   # API服务
│   ├── components/            # React组件
│   ├── hooks/                 # 自定义Hooks
│   ├── pages/                 # 页面组件
│   └── types/                 # TypeScript类型
├── tests/                     # 测试代码
└── docs/                      # 文档
```

## 快速开始

### 后端使用

```python
from backend.active_learning.strategies import get_strategy
from backend.data_quality.assessors import QualityAssessmentEngine
from backend.drift_detection.detectors import FeatureDriftDetector

# 主动学习示例
strategy = get_strategy('uncertainty', method='entropy')
tasks = [
    {'id': 1, 'data': {'text': 'hello'}},
    {'id': 2, 'data': {'text': 'world'}},
]
predictions = {
    1: [{'result': [{'value': {'choices': {'positive': 0.6, 'negative': 0.4}}}]}],
    2: [{'result': [{'value': {'choices': {'positive': 0.9, 'negative': 0.1}}}]}],
}
selected, scores = strategy.select(tasks, predictions, batch_size=1)

# 数据质量评估示例
engine = QualityAssessmentEngine(project_id=1)
report = engine.run_assessment(tasks, annotations)

# 漂移检测示例
detector = FeatureDriftDetector()
results, score, level = detector.detect(baseline_tasks, current_tasks)
```

### 前端使用

```tsx
import { DataCentricAI } from './pages';

function App() {
  return <DataCentricAI projectId={1} />;
}
```

## API参考

### Active Learning API

- `create_config(project_id, strategy, batch_size)` - 创建配置
- `select_tasks(config_id, tasks, predictions)` - 选择任务
- `get_status(project_id)` - 获取状态

### Data Quality API

- `run_assessment(project_id, tasks, annotations)` - 运行评估
- `get_dashboard(project_id)` - 获取仪表盘数据
- `resolve_issue(issue_id, user_id)` - 解决问题

### Drift Detection API

- `create_baseline(project_id, name, tasks, annotations)` - 创建基线
- `run_detection(project_id, baseline_id, current_tasks)` - 运行检测
- `acknowledge_alert(alert_id, user_id)` - 确认告警

## 测试

```bash
cd tests
python run_tests.py
```

## 许可证

MIT License
