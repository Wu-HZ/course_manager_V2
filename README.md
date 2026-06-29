# 智能排课系统

基于约束规划的自动排课系统，适用于中小学课表编排。

## 功能特性

### 基础数据管理
- **教师管理** — 送教分组、校本课程分组、周课时上下限、禁排时段、排课排除
- **班级管理** — 年级、班主任绑定
- **课程管理** — 周课时、上午优先、连堂设置、场地类型、单日上限、主课标记
- **场地管理** — 操场、实验室、家政室等特殊场地容量控制
- **送教分组** — 教师分组及禁排日设置
- **校本课程分组** — 四人教师组，周二/周四轮换
- **教师禁排时段** — 按天 + 上/下午设置教师不可排课的时段

### 排课配置
- **教师资质** — 设定教师可教授的课程（科目 × 教师网格视图）
- **授课分配** — 手动指定班级-课程-教师关系
- **课表锁定** — 预先锁定特定班级/天/节次的课程安排
- **排课参数** — 软硬约束权重、求解器配置

### 排课引擎
- 基于 Google OR-Tools CP-SAT 约束规划求解器
- 统一建模（单次 CP-SAT 求解硬约束 + 软约束目标）
- 最小硬约束集快速验证 + 全约束求解两档模式
- 无解时自动诊断最小冲突集（unsat core）
- 多线程并行求解，可配置时间上限与收敛容差
- 求解前静态预检（无合格教师等死结提前发现）

### 课表查看与导出
- 按班级 / 教师查看课表
- 教师课时分布柱状图
- 校本课程教师分组表
- Word 个人课表导出
- Excel 全量数据导入导出

### 其他
- **观课分配** — 按规则自动分配观课任务
- **响应式布局** — 适配桌面端与移动端（768px 断点）

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Element Plus + ECharts + Pinia |
| 后端 | Django 4 + Django REST Framework |
| 求解器 | Google OR-Tools (CP-SAT) |
| 数据库 | SQLite |
| 构建 | Vite 6 |
| 数据处理 | openpyxl, python-docx, xlsx |

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+

### 安装步骤

**1. 克隆项目**
```bash
git clone <repository-url>
cd course_manager
```

**2. 后端配置**
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

**3. 前端配置**
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

> **提示**：项目根目录提供了批处理脚本 `start_backend.bat` 和 `start_frontend.bat`，可直接双击启动。`clear_backend_data.bat` 可备份并清空数据库。

## 项目结构

```
course_manager/
├── backend/                     # Django 后端
│   ├── config/                  # 项目配置 (settings, urls, wsgi)
│   ├── core/                    # 核心数据模块
│   │   ├── models.py            # 数据模型 (15 个模型)
│   │   ├── views.py             # REST API 视图
│   │   ├── serializers.py       # DRF 序列化器
│   │   ├── data_io.py           # Excel 导入导出
│   │   └── admin.py             # Django Admin 注册
│   ├── scheduler/               # 排课引擎 (V2 统一 CP-SAT)
│   │   ├── service.py           # 排课编排入口 (load → build → solve → diagnose)
│   │   ├── solver.py            # CP-SAT 求解器封装
│   │   ├── repository.py        # 数据加载层 (ORM → 领域实体)
│   │   ├── diagnostics.py       # 无解诊断 (unsat core)
│   │   ├── persistence.py       # 求解结果持久化
│   │   ├── export_word.py       # Word 课表导出
│   │   ├── time_slots.py        # 时段定义
│   │   ├── engine.py            # 旧引擎 (保留回退)
│   │   ├── constraints.py       # 旧约束定义 (保留回退)
│   │   ├── models.py            # ScheduleResult / ScheduleEntry
│   │   ├── views.py             # 排课 / 预检 / 课表查询 API
│   │   ├── serializers.py       # DRF 序列化器
│   │   ├── urls.py              # 路由
│   │   ├── domain/              # 领域模型层 (纯 dataclass)
│   │   │   ├── entities.py      # 领域实体 (SubjectInfo, TeacherInfo, …)
│   │   │   ├── calendar.py      # 校历 / 时段定义
│   │   │   └── config.py        # 求解器配置值对象
│   │   ├── model/               # CP-SAT 建模层
│   │   │   ├── variables.py     # 决策变量定义
│   │   │   ├── objective.py     # 软约束目标函数 (S1–S7)
│   │   │   └── constraints/     # 硬约束族 (每族一文件)
│   │   │       ├── assignment.py       # H1 派课基数 / 联结
│   │   │       ├── exclusion.py        # H2/H3 班级 & 教师互斥
│   │   │       ├── dayoff.py           # H4 禁排日
│   │   │       ├── location.py         # H5 场地容量
│   │   │       ├── daily_limit.py      # H8 单日上限
│   │   │       ├── consecutive.py      # H9 禁连堂
│   │   │       ├── hours.py            # H10 教师周课时
│   │   │       ├── teacher_daily.py    # H11 教师同班单日上限
│   │   │       ├── blocked_time.py     # H13 教师禁排时段
│   │   │       ├── main_subject.py     # H14/H15 主课约束 & 带班数
│   │   │       └── teacher_load.py     # 教师课时上下限
│   │   └── management/commands/
│   │       └── schedule_v2.py  # Django 管理命令 (命令行排课)
│   ├── requirements.txt        # Python 依赖
│   ├── seed_data.py            # 测试数据生成
│   ├── clear_data.py           # 数据库备份清空工具
│   └── manage.py               # Django 入口
│
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── views/              # 15 个页面组件
│   │   │   ├── Dashboard.vue               # 仪表盘
│   │   │   ├── TeacherList.vue             # 教师管理
│   │   │   ├── ClassList.vue               # 班级管理
│   │   │   ├── SubjectList.vue             # 课程管理
│   │   │   ├── LocationList.vue            # 场地管理
│   │   │   ├── TravelGroupList.vue         # 送教分组
│   │   │   ├── BlockedTimeList.vue         # 教师禁排时段
│   │   │   ├── CombinedGroupList.vue       # 校本课程分组
│   │   │   ├── QualificationList.vue       # 教师资质
│   │   │   ├── AssignmentList.vue          # 授课分配
│   │   │   ├── ScheduleLockList.vue        # 课表锁定
│   │   │   ├── ScheduleRun.vue             # 执行排课
│   │   │   ├── ScheduleView.vue            # 课表查看
│   │   │   ├── SchedulerSettings.vue       # 排课参数
│   │   │   └── ObservationAssignment.vue   # 观课分配
│   │   ├── components/         # 通用组件
│   │   │   ├── AppNavMenu.vue              # 导航菜单
│   │   │   ├── TimetableGrid.vue           # 课表网格
│   │   │   ├── SchedulePrecheckPanel.vue   # 排课预检面板
│   │   │   ├── ScheduleResultPicker.vue    # 求解结果选择器
│   │   │   ├── ScheduleResultTable.vue     # 求解结果表格
│   │   │   ├── PreparationFlowCard.vue     # 准备流程卡片
│   │   │   └── MobileEntityList.vue        # 移动端列表适配
│   │   ├── api/                # Axios API 封装
│   │   ├── stores/             # Pinia 状态管理
│   │   ├── composables/        # 组合式函数 (useResponsive)
│   │   ├── utils/              # 工具函数 (precheck, scheduleResults)
│   │   ├── styles/             # 样式 (responsive.css)
│   │   ├── router/index.js     # Vue Router (15 条路由)
│   │   ├── App.vue             # 根组件
│   │   └── main.js             # 应用入口
│   ├── index.html
│   └── package.json
│
├── assets/                     # 静态资源 (Word 模板等)
├── start_backend.bat           # 一键启动后端
├── start_frontend.bat          # 一键启动前端
├── clear_backend_data.bat      # 备份并清空数据库
└── README.md
```

## 约束说明

### 硬约束（必须满足）

| 编号 | 约束 | 说明 |
|------|------|------|
| H1 | 派课基数与联结 | 每班每课每周排满指定节数；place ↔ busy 变量一致 |
| H2 | 班级互斥 | 同一班级同一时段最多一节课 |
| H3 | 教师互斥 | 同一教师同一时段最多一节课 |
| H4 | 禁排日 | 送教分组设定的禁排日不安排课程 |
| H5 | 场地容量 | 同一时段使用同一场地的课程不超过场地容量 |
| H8 | 单日上限 | 课程单日排课不超过设定上限 |
| H9 | 禁连堂 | 不允许连堂的课程不会连续排布（遵守禁排边界） |
| H10 | 教师周课时 | 教师每周课时在设定上下限范围内 |
| H11 | 教师同班单日 | 同一教师同一班级单日排课不超过上限 |
| H13 | 禁排时段 | 教师设定的禁排时段不安排课程 |
| H14 | 班主任主课 | （可选）班主任必须担任所带班级的主课 |
| H15 | 主课门数上限 | 单师最多担任的主课门数 |

### 软约束（尽量满足）

| 编号 | 约束 | 说明 |
|------|------|------|
| S1 | 上午优先 | 标记为"上午优先"的课程尽量排在上午（奖励） |
| S2 | 连堂偏好 | 允许连堂的课程连续排列（奖励） |
| S3 | 同天分散 | 同一课程在同一班级同一天尽量不超过 1 节（惩罚超出） |
| S4 | 教师日课时均衡 | 教师单日课时超过阈值时惩罚超出部分 |
| S5 | 避免第一节 | 标记为"避免第一节"的课程不排在第 1 节（惩罚） |
| S6 | 减少换班 | 教师连续两节在不同班级授课时惩罚 |
| S7 | 减少换科 | 教师连续两节在同一班级但换科目时惩罚 |

> 所有软约束权重可在"排课参数"页面独立调节，设为 0 即禁用该项。

## 服务器配置建议

| 规模 | 配置建议 |
|------|----------|
| 小型 (<10 班) | 2 核 4G |
| 中型 (10–30 班) | 4 核 8G |
| 大型 (30+ 班) | 8 核 16G |

> 排课求解时 CPU 占用较高，平时仅运行 Web 服务资源消耗很低。

## 许可证

MIT License
