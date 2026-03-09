# 智能排课系统

基于约束规划的自动排课系统，适用于中小学课表编排。

## 功能特性

### 基础数据管理
- **教师管理** - 送教分组、校本课程分组、周课时限制
- **班级管理** - 年级、班主任绑定
- **课程管理** - 周课时、上午优先、连堂设置、场地类型、单日上限
- **场地管理** - 操场、实验室、家政室等特殊场地容量控制
- **送教分组** - 教师禁排日设置
- **校本课程分组** - 教师分组及周二/周四轮换

### 排课配置
- **教师资质** - 设定教师可教授的课程
- **授课分配** - 手动指定班级-课程-教师关系
- **课表锁定** - 预先锁定特定时段的课程安排
- **排课参数** - 软硬约束权重、求解器配置

### 排课引擎
- 基于 Google OR-Tools CP-SAT 约束规划求解器
- 支持多种硬约束（教师冲突、场地容量、禁排日等）
- 支持多种软约束（上午优先、连堂偏好、负载均衡等）
- 自动诊断无解原因
- 多线程并行求解

### 课表查看
- 按班级/教师查看课表
- 教师课时分布柱状图
- 校本课程教师分组表

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Element Plus + ECharts |
| 后端 | Django 4 + Django REST Framework |
| 求解器 | Google OR-Tools (CP-SAT) |
| 数据库 | SQLite |

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd course_manager
```

2. **后端配置**
```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scripts\activate
# 激活虚拟环境 (Linux/Mac)
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 数据库迁移
python manage.py migrate

# (可选) 导入测试数据
python seed_data.py
```

3. **前端配置**
```bash
cd frontend

# 安装依赖
npm install
```

### 启动服务

**后端** (端口 8001)
```bash
cd backend
venv\Scripts\python manage.py runserver 8001
```

**前端** (端口 5173)
```bash
cd frontend
npm run dev
```

访问 http://localhost:5173

## 项目结构

```
course_manager/
├── backend/                # Django 后端
│   ├── config/            # 项目配置
│   ├── core/              # 核心模块 (模型、API)
│   │   ├── models.py      # 数据模型
│   │   ├── views.py       # API 视图
│   │   └── serializers.py # 序列化器
│   ├── scheduler/         # 排课引擎
│   │   ├── engine.py      # 核心算法
│   │   ├── constraints.py # 约束定义
│   │   └── views.py       # 排课 API
│   └── requirements.txt   # Python 依赖
│
├── frontend/              # Vue 前端
│   ├── src/
│   │   ├── views/        # 页面组件
│   │   ├── components/   # 通用组件
│   │   └── api/          # API 封装
│   └── package.json      # Node 依赖
│
└── README.md
```

## 约束说明

### 硬约束 (必须满足)
- 教师在同一时段只能上一节课
- 班级在同一时段只能上一节课
- 教师禁排日不安排课程
- 特殊场地容量限制
- 班会课锁定 (周五第4节)
- 校本课程锁定 (周二/四下午)

### 软约束 (尽量满足)
- 上午优先课程排在上午
- 允许连堂的课程连续安排
- 同一课程在一周内分布均匀
- 教师每日课时负载均衡
- 避免第一节课安排特定课程
- 减少教师频繁换班

## 服务器配置建议

| 规模 | 配置建议 |
|------|----------|
| 小型 (<10班) | 2核4G |
| 中型 (10-30班) | 4核8G |
| 大型 (30+班) | 8核16G |

> 排课求解时 CPU 占用较高，平时仅运行 Web 服务资源消耗很低。

## 许可证

MIT License
