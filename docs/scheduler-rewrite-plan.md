# 排课引擎重构方案：联合 CP-SAT 模型（派课 + 排时间）

> 适用对象：在**新项目**中重写排课核心。沿用旧项目的 Django 数据模型、导入导出、预检、前端 UI 与约束语义（H1–H15 / S1–S7），但**完全重写排课引擎**。本文件自包含，可脱离原始对话执行。

---

## 1. Context：为什么要重构

旧项目 `backend/scheduler/engine.py`（单文件 1470 行、God Class）把排课拆成两段，再用随机重试缝合：

1. `auto_assign_teachers()`：**贪心 + `random.shuffle`** 把老师派给 (班级, 课程)，完全不考虑时间约束。
2. CP-SAT：在派课定死的前提下只求时间表。
3. `run_scheduler()`：第二阶段无解就**换随机种子整体重来，最多 50 次**。

**根本错误**：派课与排时间是同一个耦合的约束满足问题，被人为切成两半。第一阶段在不知道禁排日/连堂/互斥的情况下贪心派课，常派出"排不进时间表"的方案，再靠随机重试去赌。证据：`self.teacher_choice_vars`（让 CP-SAT 决定派课的变量）在 `__init__` 声明后**全程未用**——最初想联合建模，后来放弃了。

由此产生的、已在实际使用中确认的后果：
- **不确定**：同样数据时成时不成（随机）。
- **无法诊断**：求解器拿到的是"被派死的"输入，它的 INFEASIBLE 不可信；于是不得不手写约 390 行 `analyze_infeasibility` 去**猜**，而那些只是必要非充分的启发式，抓不到真正的组合死结。典型现象：50 次里 49 次 INFEASIBLE + 1 次"无法分配教师"——系统自己都分不清是真无解还是这次随机派得差。
- **浪费**：5 个班的规模，本应秒解，却把整模型建 50 遍、每次最多 300 秒。

**重构目标**：把派课变成求解器的决策变量，与排时间**联合求解**。这样要么给可行解、要么**证明**无解并给出最小冲突集（unsat core），随机重试与大部分手写诊断都可删除。

---

## 2. 核心：联合 CP-SAT 模型

### 2.1 符号
- `C` 班级集合；`S` 课程集合；`T` 教师集合；`Slots = {(d,p)}` 时间片。
- `active(c,s)`：班 c 需要开课 s（按年级适用性），周课时 `h(s)`。
- `qual(s)`：有资质教 s 的教师集合。
- 普通课程才进模型；班会、校本课程仍按旧逻辑**预锁定**（见 §4）。

### 2.2 决策变量
- `assign[c,s,t] ∈ {0,1}`：班 c 的课 s 由教师 t 上。**仅对 `t ∈ qual(s)` 创建**。
- `place[c,s,d,p] ∈ {0,1}`：(c,s) 占用时间片 (d,p)。仅对合法时间片创建（跳过班会/校本锁定片、禁排片）。
- `busy[c,s,t,d,p] ∈ {0,1}`：派课与排时的联结变量 = `assign[c,s,t] ∧ place[c,s,d,p]`。仅对 `t ∈ qual(s)` 且合法 (d,p) 创建。
  - 用 reification 建立：`AddBoolAnd([assign, place]).OnlyEnforceIf(busy)` + `AddBoolOr([assign.Not(), place.Not()]).OnlyEnforceIf(busy.Not())`。
  - 规模量级（5 班 ×~12 课 ×15 师 ×28 片 ≈ 2.5 万布尔）对 CP-SAT 微不足道。

### 2.3 硬约束（全部写进同一模型）
| 约束 | 公式 |
|---|---|
| 每个 active(c,s) 恰好一位老师 | `sum_{t∈qual(s)} assign[c,s,t] == 1` |
| 周课时 | `sum_{d,p} place[c,s,d,p] == h(s)`（扣除已锁定） |
| 班级互斥（H2） | `∀c,d,p: sum_s place[c,s,d,p] ≤ 1` |
| 教师互斥（H3） | `∀t,d,p: sum_{c,s} busy[c,s,t,d,p] ≤ 1` |
| place 与 assign 联结 | `∀c,s,d,p: sum_{t} busy[c,s,t,d,p] == place[c,s,d,p]`（被排的课由其指派教师上） |
| 单师最多带班数 | `∀s,t: sum_c assign[c,s,t] ≤ max_teacher_classes(s)` |
| 单师最多主课数（H15） | 引入 `teaches[s,t]=OR_c assign[c,s,t]`；`∀t: sum_{s∈main} teaches[s,t] ≤ h15` |
| 班主任必须担任主课（H14） | 班 c 的班主任 t：`sum_{s∈main} assign[c,s,t] ≥ 1`（可设为开关） |
| 教师周课时上下限（H10） | `∀t: min_h(t) ≤ sum_{c,s} assign[c,s,t]·h(s) ≤ max_h(t)`（**线性，替代贪心负载跟踪**） |
| 禁排日（H4）/禁排时段（H13） | 对禁止的 (t,d,p)：不创建该 t 的 `busy[*,*,t,d,p]`（或置 0） |
| 连续禁排边界（H9） | `∀t,d,边界(p1,p2): sum_{c,s}(busy[c,s,t,d,p1]+busy[c,s,t,d,p2]) ≤ 1` |
| 教师同班单日上限（H11） | `∀t,c,d: sum_{s,p} busy[c,s,t,d,p] ≤ h11` |
| 课程单日上限（H8） | `∀c,s,d: sum_p place[c,s,d,p] ≤ max_daily(s)` |
| 场地容量（H5） | `∀场地类型,d,p: sum_{(c,s)用该场地} place[c,s,d,p] ≤ capacity` |

> 关键收益：H10/H11/H14/H15/单师带班数等"派课层规则"全部成了 **assign 上的线性约束**，与排时间联合求解——不再有贪心、随机、重试。

### 2.4 软约束 / 目标（S1–S7）
- 语义沿用旧定义（上午优先、连堂偏好、分布均匀、教师日负载、避免第一节、换班/换科惩罚）。
- 用 `place`/`busy` 重新表达（多数本就基于 place）。
- **重新评估加权和 vs 字典序**：旧实现是手调权重相加，冲突时取舍不可控。建议至少分两层——先满足硬约束，再在"教师均衡类"与"学生体验类"之间用**字典序或可配置优先级**，权重含义写进文档。
- 目标：`Maximize(sum 奖励 − sum 惩罚)`，保留 settings 中的权重字段。

### 2.5 诊断：用 assumptions 拿 unsat core（替代手写 390 行）
- 把"可能导致无解、且想解释给用户"的硬约束包成 **assumption 文字**（`model.AddAssumption(lit)` 或对约束加 `OnlyEnforceIf(lit)`）。建议至少给：每教师课时上下限、每班周课时、禁排日整体、H11、H14。
- 无解时调用 `solver.SufficientAssumptionsForInfeasibility()` 得最小冲突集，映射回中文约束描述。
- 这把"猜原因"变成"求解器证明的原因"。旧 `analyze_infeasibility` 的绝大部分可删；仅保留少量**纯静态的、求解前预检**（如某课无资质教师、某课合格教师×带班数<班级数——这些是确定性且无需求解的）。

---

## 3. 代码结构（拆掉 God Class）

新项目按职责分层，领域逻辑与 Django 解耦：

```
scheduler/
  domain/            # 纯数据结构（dataclass），不依赖 Django
    entities.py      # Class, Subject, Teacher, Slot, Assignment...
    calendar.py      # 时间结构：PERIODS_PER_DAY / AM_PERIODS / 班会片 / 校本片 —— 参数化（见 §5）
  repository.py      # 从 Django ORM 读出 → domain 对象（唯一与 ORM 耦合处）
  model/
    variables.py     # 建 assign / place / busy
    constraints/     # 每族约束一文件：hours.py, exclusion.py, teacher_load.py,
                     #   main_subject.py, dayoff.py, location.py ...
    objective.py     # S1–S7
  solver.py          # 组装模型、求解、抽取解
  diagnostics.py     # unsat core 映射 + 求解前静态预检
  service.py         # 编排：load → build → solve → (diagnose|persist)。替代旧 run()
  persistence.py     # 解 → ScheduleResult/Entry 落库
```

原则：`domain` 与 `model` 不 import Django；ORM 只出现在 `repository.py` / `persistence.py`。每族约束可独立单元测试（给最小 model + 变量，断言可行/不可行）。

---

## 4. 移植 / 重写 / 删除清单

**直接沿用（不动）**：Django models、serializers、导入导出（`data_io.py`）、前端全部、约束**语义**定义（H1–H15、S1–S7）、SchedulerSettings 字段。

**移植但重写实现**：约束逻辑（从 `constraints.py` 的语义平移到 `model/constraints/`，但基于 assign/place 重新表达）。

**整体重写**：`engine.py` → 上述分层结构。

**删除**：
- `auto_assign_teachers()` 贪心派课（约 265 行）。
- `run_scheduler()` 的 50 次随机重试循环。
- `teacher_choice_vars` 死代码。
- `analyze_infeasibility()` 绝大部分（约 390 行），保留少量静态预检迁入 `diagnostics.py`。
- 所有 `random.*`（派课不再随机）。

**校本课程轮值（assign_combined_class_teachers）**：这是 Tue/Thu 的独立子问题，**第一期保持独立预处理**，先锁定时段再进主模型（与班会一样作为预锁定输入）。第二期再评估是否并入。

---

## 5. 顺带修掉的旧债（重写时几乎零成本）

既然重建领域层，把这些写死项参数化进 `domain/calendar.py` 与 settings：
- `PERIODS_PER_DAY`（每天节数）、`AM_PERIODS`（上午节数）。
- 班会时段（旧：周五第 4 节写死）。
- 校本课程日（旧：周二/周四写死，且与可配置的"合班时段"打架）。
- 校本必须恰好 ≥4 组（旧写死）。

> 注意 scope：可先只把 `PERIODS_PER_DAY`/`AM_PERIODS` 参数化（被几乎所有约束引用），其余按需。避免一次性铺太大。

---

## 6. 安全迁移策略（影子模式）

旧项目"能用"，不要直接切。新项目里：

1. **第 1 期**：搭分层骨架 + 联合模型，只跑硬约束（H1–H15），目标先留空或最简。能对一份真实数据**给出可行解或证明无解**即里程碑。
2. **第 2 期**：加入 S1–S7 目标与权重；加 unsat core 诊断。
3. **影子对比**：用旧项目导出的真实数据集（**务必包含那个 5 班、当前排不出的数据集**）跑新引擎，对比：(a) 旧的随机重试结果 vs 新解；(b) 旧说"无解"时新引擎是真无解还是能解。
4. **验收标准**：
   - 旧引擎需 N 次随机才偶尔排出的数据，新引擎**一次确定性**排出。
   - 旧引擎反复 INFEASIBLE 的数据，新引擎要么排出、要么给出**可读的最小冲突集**。
   - 同规模求解时间显著下降（预期秒级）。
5. **切换**：新引擎稳定后，替换排课 API 端点；前端基本不动（输入输出契约保持一致）。

---

## 7. 风险与注意

- **bilinear 联结**：`busy = assign ∧ place` 的 reification 会增加变量数；5 班规模无虞，但需在 §8 验证更大规模的可扩展性，必要时改用更紧的建模（如按时段聚合）。
- **目标重调**：联合模型的"最优"分布会变，S1–S7 权重需重新调，并补文档说明取舍。
- **校本/班会预锁定**：必须先于主模型确定其占用，作为 place 的固定输入。
- **数据契约**：保持排课结果的 ScheduleResult/Entry 结构不变，前端与导出零改动。

---

## 8. 验证

- **单元**：每族约束独立测试（给最小变量集，断言 feasible/infeasible 与期望一致）。
- **集成**：
  - 资质瓶颈（某课合格教师×带班数<班级数）→ 模型 INFEASIBLE 且 unsat core 指向该课。
  - 禁排日失衡的满载数据 → 验证新引擎行为（解出 / 给冲突集），与旧引擎对比。
  - H14/H15 开关在模型层生效（与旧引擎测试对齐）。
- **回归**：用旧项目导出的真实数据集做影子对比（§6.3）。
- **性能**：记录变量/约束规模与求解耗时，确认秒级。

---

## 9. 第一步（建议从这里动手）

1. 新项目搭 `domain/` + `repository.py`，把一份真实数据读成 domain 对象。
2. 写 `model/variables.py`（assign/place/busy）+ 最小硬约束（周课时、班级互斥、教师互斥、资质、禁排日）。
3. `solver.py` 跑通：对那份 5 班数据输出可行解或 INFEASIBLE。
4. 跑通后再逐族加 H5/H8/H9/H10/H11/H14/H15，最后加 S1–S7 与诊断。

> 一句话验收：**当那份"旧引擎跑 50 次都排不出"的数据，在新引擎下要么一次排出、要么告诉你到底是哪几条约束打架——重构就成功了。**
