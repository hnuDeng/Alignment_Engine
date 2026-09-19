# 指令 08：API集成与路由配置

## 目标

将所有新模块的URL路由集成到Label Studio主路由系统中，并配置必要的settings。

## 需要修改的文件

1. `label_studio/core/urls.py` - 主URL配置
2. `label_studio/core/settings/base.py` - Django设置
3. `web/apps/labelstudio/src/routes/index.tsx` - 前端路由

## 详细实现

### 8.1 后端URL集成

修改 `label_studio/core/urls.py`，添加新模块的URL：

```python
# label_studio/core/urls.py

from django.urls import path, include
from django.contrib import admin

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 原有的URL配置...
    path('', include('core.urls_original')),
    
    # 新增模块URL
    path('', include('active_learning.urls')),
    path('', include('data_quality.urls')),
    path('', include('drift_detection.urls')),
]
```

### 8.2 Django Settings配置

在 `label_studio/core/settings/base.py` 中添加：

```python
# label_studio/core/settings/base.py

# 在INSTALLED_APPS中添加新应用
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # 第三方应用
    'rest_framework',
    'django_filters',
    'drf_spectacular',
    
    # Label Studio原有应用
    'core',
    'users',
    'projects',
    'tasks',
    'ml',
    'data_manager',
    'data_import',
    'data_export',
    'io_storages',
    'organizations',
    'labels_manager',
    'webhooks',
    
    # 新增应用
    'active_learning',
    'data_quality',
    'drift_detection',
]

# REST Framework配置
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# DRF Spectacular配置（API文档）
SPECTACULAR_SETTINGS = {
    'TITLE': 'Label Studio Data-Centric AI API',
    'DESCRIPTION': 'API for Data-Centric AI workflow in Label Studio',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

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

### 8.3 前端路由集成

修改前端路由配置，添加Data-Centric AI页面：

```tsx
// web/apps/labelstudio/src/routes/index.tsx

import { createBrowserRouter } from 'react-router-dom';
import { DataCentricAI } from '../pages/DataCentricAI';

// ... 其他路由导入

export const router = createBrowserRouter([
  // ... 原有路由
  
  {
    path: '/projects/:projectId/data-centric-ai',
    element: <DataCentricAIWrapper />,
  },
  
  // ... 其他路由
]);

// 包装组件，从URL获取projectId
function DataCentricAIWrapper() {
  const { projectId } = useParams();
  return <DataCentricAI projectId={Number(projectId)} />;
}
```

### 8.4 添加导航入口

在项目详情页面添加Data-Centric AI入口：

```tsx
// web/apps/labelstudio/src/pages/ProjectDetail/Navigation.tsx

import { Brain, Shield, TrendingUp } from 'lucide-react';

// 在项目导航中添加
const projectNavItems = [
  // ... 原有导航项
  {
    key: 'data-centric-ai',
    label: 'Data-Centric AI',
    icon: Brain,
    path: `/projects/${projectId}/data-centric-ai`,
  },
];
```

### 8.5 数据库迁移

```bash
# 生成迁移文件
python label_studio/manage.py makemigrations active_learning
python label_studio/manage.py makemigrations data_quality
python label_studio/manage.py makemigrations drift_detection

# 执行迁移
python label_studio/manage.py migrate
```

## 验证检查点

- [ ] 后端URL路由配置正确
- [ ] Django settings配置完成
- [ ] 前端路由配置正确
- [ ] 数据库迁移执行成功
- [ ] 导航入口可访问

## 下一步

执行 `09_testing.md` 进行测试实现。
