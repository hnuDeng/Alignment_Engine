# 指令 01：项目环境搭建

## 目标

搭建Label Studio二次开发环境，配置必要的依赖和工具。

## 前置条件

- Python 3.9+
- Node.js 18+
- Git
- PostgreSQL（可选，SQLite也可用于开发）

## 步骤

### 1.1 克隆Label Studio仓库

```bash
# 克隆官方仓库
git clone https://github.com/HumanSignal/label-studio.git
cd label-studio

# 创建开发分支
git checkout -b feature/data-centric-ai
```

### 1.2 后端环境配置

```bash
# 创建Python虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装基础依赖
pip install -e .

# 安装数据为中心AI新增依赖
pip install scikit-learn>=1.3.0
pip install scipy>=1.11.0
pip install numpy>=1.24.0
pip install pandas>=2.0.0
pip install alibi-detect>=0.11.0
pip install umap-learn>=0.5.4
pip install hdbscan>=0.8.33
```

### 1.3 前端环境配置

```bash
# 进入前端目录
cd web

# 安装依赖（使用bun或npm）
bun install
# 或
npm install

# 安装新增前端依赖
bun add recharts@^2.8.0
bun add d3@^7.8.0
bun add @types/d3
bun add @radix-ui/react-tabs
bun add @radix-ui/react-select
bun add @radix-ui/react-dialog
bun add @radix-ui/react-progress
bun add @radix-ui/react-tooltip
bun add lucide-react
```

### 1.4 数据库配置

```bash
# 回到项目根目录
cd ..

# 创建数据库迁移
python label_studio/manage.py makemigrations

# 执行迁移
python label_studio/manage.py migrate

# 创建超级用户
python label_studio/manage.py createsuperuser
```

### 1.5 创建新模块目录结构

```bash
# 创建主动学习模块
mkdir -p label_studio/active_learning/strategies
mkdir -p label_studio/active_learning/selectors
mkdir -p label_studio/active_learning/migrations
mkdir -p label_studio/active_learning/tests

# 创建数据质量模块
mkdir -p label_studio/data_quality/assessors
mkdir -p label_studio/data_quality/reporters
mkdir -p label_studio/data_quality/migrations
mkdir -p label_studio/data_quality/tests

# 创建漂移检测模块
mkdir -p label_studio/drift_detection/detectors
mkdir -p label_studio/drift_detection/monitors
mkdir -p label_studio/drift_detection/alerts
mkdir -p label_studio/drift_detection/migrations
mkdir -p label_studio/drift_detection/tests

# 创建前端页面目录
mkdir -p web/apps/labelstudio/src/pages/DataCentricAI/ActiveLearning
mkdir -p web/apps/labelstudio/src/pages/DataCentricAI/DataQuality
mkdir -p web/apps/labelstudio/src/pages/DataCentricAI/DriftDetection
mkdir -p web/apps/labelstudio/src/pages/DataCentricAI/components
```

### 1.6 配置settings.py

在 `label_studio/core/settings/base.py` 中添加新应用：

```python
# 在 INSTALLED_APPS 中添加
INSTALLED_APPS = [
    ...
    'active_learning',
    'data_quality',
    'drift_detection',
]
```

### 1.7 验证环境

```bash
# 启动后端开发服务器
python label_studio/manage.py runserver

# 在另一个终端启动前端
cd web
bun start
# 或
npm start

# 访问 http://localhost:8080 验证服务启动
```

## 检查点

- [ ] Label Studio仓库克隆成功
- [ ] Python虚拟环境创建并激活
- [ ] 后端依赖安装完成
- [ ] 前端依赖安装完成
- [ ] 数据库迁移执行成功
- [ ] 新模块目录结构创建完成
- [ ] Django settings配置完成
- [ ] 开发服务器启动成功

## 输出

完成此步骤后，你应该有一个可运行的Label Studio开发环境，所有新模块目录已创建。

## 下一步

执行 `02_active_learning_backend.md` 创建主动学习后端模块。
