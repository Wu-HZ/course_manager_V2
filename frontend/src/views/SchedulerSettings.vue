<template>
  <div class="settings-page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2>排课参数设置</h2>
        <p class="page-subtitle">
          这些参数会影响排课规则与评分方式。一般保持默认即可；保存后仅影响后续排课，不会改动已有结果。
        </p>
      </div>
      <div class="page-header__actions">
        <el-button plain @click="handleReset">恢复默认值</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存设置</el-button>
      </div>
    </div>

    <div class="summary-strip">
      <div class="summary-strip__text">重点关注班会课程名、合班课时段、教师连续上课边界和软约束权重。</div>
      <div class="summary-strip__stats">
        <span v-for="item in overviewStats" :key="item.label" class="summary-chip">
          <strong>{{ item.value }}</strong>
          <span>{{ item.label }}</span>
        </span>
      </div>
    </div>

    <div class="section-stack">
      <section v-for="section in sections" :key="section.key" class="section-card">
        <div class="section-header">
          <div>
            <div class="section-title">{{ section.title }}</div>
            <div class="section-subtitle">{{ section.subtitle }}</div>
          </div>
          <el-tag size="small" effect="plain" round>{{ section.count }} 项</el-tag>
        </div>

        <template v-if="section.groups">
          <div class="section-groups">
            <div v-for="group in section.groups" :key="group.key" class="section-group">
              <div class="section-group__header">
                <div>
                  <div class="section-group__title">{{ group.title }}</div>
                  <div class="section-group__subtitle">{{ group.subtitle }}</div>
                </div>
                <el-tag size="small" effect="plain" round>{{ group.fields.length }} 项</el-tag>
              </div>

              <div class="field-grid" :class="group.gridClass">
                <div
                  v-for="field in group.fields"
                  :key="field.key"
                  class="field-card"
                  :class="field.spanClass"
                >
                  <div class="field-card__head">
                    <div class="field-card__code">{{ field.code }}</div>
                    <div class="field-card__label">{{ field.label }}</div>
                  </div>

                  <div class="field-card__control">
                    <el-input
                      v-if="field.type === 'text'"
                      v-model="form[field.key]"
                      :placeholder="field.placeholder || ''"
                      clearable
                    />
                    <div v-else-if="field.type === 'switch'" class="switch-control">
                      <el-switch v-model="form[field.key]" />
                      <span class="field-card__unit">{{ form[field.key] ? '已启用' : '已关闭' }}</span>
                    </div>
                    <div v-else class="number-control">
                      <el-input-number
                        v-model="form[field.key]"
                        :min="field.min"
                        :max="field.max"
                      />
                      <span v-if="field.unit" class="field-card__unit">{{ field.unit }}</span>
                    </div>
                  </div>

                  <div class="field-card__help">{{ field.help }}</div>
                  <div v-if="field.note" class="field-card__note">{{ field.note }}</div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <div v-else class="field-grid" :class="section.gridClass">
          <div
            v-for="field in section.fields"
            :key="field.key"
            class="field-card"
            :class="field.spanClass"
          >
            <div class="field-card__head">
              <div class="field-card__code">{{ field.code }}</div>
              <div class="field-card__label">{{ field.label }}</div>
            </div>

            <div class="field-card__control">
              <el-input
                v-if="field.type === 'text'"
                v-model="form[field.key]"
                :placeholder="field.placeholder || ''"
                clearable
              />
              <div v-else-if="field.type === 'switch'" class="switch-control">
                <el-switch v-model="form[field.key]" />
                <span class="field-card__unit">{{ form[field.key] ? '已启用' : '已关闭' }}</span>
              </div>
              <div v-else class="number-control">
                <el-input-number
                  v-model="form[field.key]"
                  :min="field.min"
                  :max="field.max"
                />
                <span v-if="field.unit" class="field-card__unit">{{ field.unit }}</span>
              </div>
            </div>

            <div class="field-card__help">{{ field.help }}</div>
            <div v-if="field.note" class="field-card__note">{{ field.note }}</div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const basicFields = [
  {
    key: 'class_meeting_name',
    code: 'BASE-1',
    label: '班会课程名',
    type: 'text',
    help: '用于识别哪门课程应视为班会课。',
    note: '匹配到的课程会固定锁定在周五第 4 节，由班主任承担，并且不进入教师资质和授课分配。请与课程名称完全一致，例如：班会、班队会、主题班会。',
  },
  {
    key: 'combined_class_slots',
    code: 'BASE-2',
    label: '合班课时段',
    type: 'text',
    spanClass: 'field-card--span-2',
    help: '定义全校统一预留给校本课程/合班课的固定时段。',
    note: '这些时间片会先锁给校本课程，普通课程不会排到这里；参与校本课程分组的教师在这些时段也会被占用。格式示例：1,4;1,5;3,4;3,5。星期从 0=周一开始，节次从 0 开始。',
  },
  {
    key: 'solver_num_workers',
    code: 'BASE-3',
    label: '求解器线程数',
    type: 'number',
    min: 1,
    max: 16,
    help: '控制 OR-Tools 求解器并行搜索使用的线程数。',
    note: '通常建议接近机器可用 CPU 核心数。它影响求解速度和资源占用，不直接改变约束或评分规则。',
  },
]

const hardConstraintFields = [
  {
    key: 'h9_consecutive_forbidden',
    code: 'H9',
    label: '教师禁止跨边界连续上课',
    type: 'text',
    help: '对同一教师生效，禁止他在指定边界两侧连续上课，不区分是否连堂，也不区分是否同一个班级。',
    note: '例如 1,2 表示同一教师不能同时占用第 2、3 节；例如 3,4 表示不能跨第 4、5 节连续上课。格式示例：1,2;3,4，索引从 0 开始。',
  },
  {
    key: 'h11_teacher_class_daily_max',
    code: 'H11',
    label: '教师同班单日上限',
    type: 'number',
    min: 1,
    max: 6,
    unit: '节',
    help: '限制同一教师在同一天、同一班级的总排课节数。',
    note: '这是按“教师 + 班级 + 日期”汇总计算的，不区分该教师在这个班教的是哪一门课。过小会增加排课难度，过大则可能让课表过于集中。',
  },
  {
    key: 'h14_homeroom_main_subject',
    code: 'H14',
    label: '班主任必须担任主课',
    type: 'switch',
    spanClass: 'field-card--span-2',
    help: '开启后，每个班级的班主任必须在本班至少担任一门主课，否则排课会失败。',
    note: '系统会优先把主课分配给班主任。若该班主任没有任何主课资质、或主课已被占满，将无法排课。关闭后班主任与普通教师一样参与分配，不再强制担任主课。',
  },
  {
    key: 'h15_teacher_max_main_subjects',
    code: 'H15',
    label: '单师最多主课数',
    type: 'number',
    min: 1,
    max: 5,
    unit: '门',
    help: '同一教师最多可担任几门不同的主课科目（如语文、数学算两门）。',
    note: '默认 1，即一个教师只能教一门主课。教同一门主课的多个班级不计入此上限，由课程的“单师最多班数”单独控制。',
  },
]

const preferenceRewardFields = [
  {
    key: 's1_am_preference_weight',
    code: 'S1',
    label: '上午优先权重',
    type: 'number',
    min: 0,
    max: 100,
    help: '对标记为“上午优先”的课程，每排到上午 1 节就增加一份奖励分。',
  },
  {
    key: 's2_consecutive_weight',
    code: 'S2',
    label: '连堂偏好权重',
    type: 'number',
    min: 0,
    max: 100,
    help: '对“允许连堂”的课程，每形成一组允许的相邻连排，就增加一份奖励分。',
  },
]

const preferencePenaltyFields = [
  {
    key: 's3_distribution_weight',
    code: 'S3',
    label: '分布均匀权重',
    type: 'number',
    min: 0,
    max: 100,
    help: '同一班级的同一门课在同一天超过 1 节时，对超出的节数累计惩罚。',
  },
  {
    key: 's4_teacher_daily_threshold',
    code: 'S4-A',
    label: '教师日负载阈值',
    type: 'number',
    min: 1,
    max: 6,
    unit: '节',
    help: '教师某天总排课节数超过该值后，才开始计算日负载惩罚。',
  },
  {
    key: 's4_teacher_daily_weight',
    code: 'S4-B',
    label: '教师日负载权重',
    type: 'number',
    min: 0,
    max: 100,
    help: '教师某天总排课每超出阈值 1 节，就增加一份惩罚分。',
  },
  {
    key: 's5_avoid_first_weight',
    code: 'S5',
    label: '避免第一节权重',
    type: 'number',
    min: 0,
    max: 100,
    help: '对标记为“避免第一节”的课程，每排在当天第 1 节 1 次，就增加一份惩罚分。',
  },
  {
    key: 's6_subject_switch_weight',
    code: 'S6',
    label: '换班惩罚权重',
    type: 'number',
    min: 0,
    max: 100,
    help: '同一教师若上一节在 A 班、下一节在 B 班，就记一次惩罚分。',
  },
  {
    key: 's7_same_class_subject_switch_weight',
    code: 'S7',
    label: '同班换科惩罚权重',
    type: 'number',
    min: 0,
    max: 100,
    help: '同一教师若连续两节在同一班级但教授不同科目，就记一次惩罚分；同科连堂不罚。',
  },
]

const sections = [
  {
    key: 'basic',
    title: '基础配置',
    subtitle: '决定班会识别、合班课时段以及求解器并行方式。',
    count: basicFields.length,
    gridClass: 'field-grid--basic',
    fields: basicFields,
  },
  {
    key: 'constraints',
    title: '硬约束参数',
    subtitle: '必须满足的限制，调整后会直接影响是否能够排通。',
    count: hardConstraintFields.length,
    gridClass: 'field-grid--constraints',
    fields: hardConstraintFields,
  },
  {
    key: 'preferences',
    title: '软约束权重',
    subtitle: '只在多个方案都可行时参与评分，区分奖励分与惩罚分后会更容易调整取舍方向。',
    count: preferenceRewardFields.length + preferencePenaltyFields.length,
    groups: [
      {
        key: 'reward',
        title: '奖励分',
        subtitle: '数值越大，系统越倾向于主动争取这类安排。',
        gridClass: 'field-grid--reward',
        fields: preferenceRewardFields,
      },
      {
        key: 'penalty',
        title: '惩罚分',
        subtitle: '数值越大，系统越会回避这类安排；阈值项用于决定惩罚何时开始生效。',
        gridClass: 'field-grid--penalty',
        fields: preferencePenaltyFields,
      },
    ],
  },
]

const overviewStats = [
  { label: '基础配置', value: basicFields.length },
  { label: '硬约束', value: hardConstraintFields.length },
  { label: '软约束', value: preferenceRewardFields.length + preferencePenaltyFields.length },
]

const loading = ref(false)
const saving = ref(false)
const form = ref({
  class_meeting_name: '班会',
  combined_class_slots: '1,4;1,5;3,4;3,5',
  solver_num_workers: 4,
  h9_consecutive_forbidden: '1,2;3,4',
  h11_teacher_class_daily_max: 2,
  h14_homeroom_main_subject: true,
  h15_teacher_max_main_subjects: 1,
  s1_am_preference_weight: 10,
  s2_consecutive_weight: 5,
  s3_distribution_weight: 2,
  s4_teacher_daily_threshold: 3,
  s4_teacher_daily_weight: 8,
  s5_avoid_first_weight: 6,
  s6_subject_switch_weight: 5,
  s7_same_class_subject_switch_weight: 3,
})

const loadSettings = async () => {
  loading.value = true
  try {
    const data = await api.get('/scheduler-settings/')
    form.value = data
  } catch (e) {
    ElMessage.error('加载设置失败')
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    await api.put('/scheduler-settings/update/', form.value)
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleReset = async () => {
  await ElMessageBox.confirm('确定恢复所有参数为默认值？', '提示', { type: 'warning' })
  try {
    const data = await api.post('/scheduler-settings/reset/')
    form.value = data
    ElMessage.success('已恢复默认值')
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

onMounted(loadSettings)
</script>

<style scoped>
.settings-page {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 14px;
}

.page-header h2 {
  margin: 0;
  color: #303133;
}

.page-subtitle {
  margin: 6px 0 0;
  max-width: 760px;
  font-size: 14px;
  line-height: 1.7;
  color: #606266;
}

.page-header__actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.summary-strip {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid #ebeef5;
  border-radius: 14px;
  background: #fafbfd;
}

.summary-strip__text {
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.summary-strip__stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.summary-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  border: 1px solid #e4eaf1;
  border-radius: 999px;
  background: #fff;
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
}

.summary-chip strong {
  font-size: 14px;
  color: #2f5f8a;
}

.section-stack {
  display: grid;
  gap: 16px;
}

.section-card {
  border: 1px solid #ebeef5;
  border-radius: 16px;
  background: #fff;
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid #f0f3f7;
  background: #fbfcfe;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.section-subtitle {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.field-grid {
  display: grid;
  gap: 12px;
  padding: 16px;
}

.section-groups {
  display: grid;
  gap: 12px;
  padding: 16px;
}

.section-group {
  border: 1px solid #edf1f6;
  border-radius: 14px;
  background: #fcfdff;
  overflow: hidden;
}

.section-group__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid #eef2f6;
  background: #f8fafc;
}

.section-group__title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.section-group__subtitle {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: #606266;
}

.field-grid--basic,
.field-grid--constraints {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.field-grid--reward {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.field-grid--penalty {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.field-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  padding: 14px;
  border: 1px solid #edf1f6;
  border-radius: 12px;
  background: #fcfdff;
}

.field-card--span-2 {
  grid-column: span 2;
}

.field-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.field-card__code {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef3f8;
  font-size: 12px;
  font-weight: 700;
  color: #6f8399;
}

.field-card__label {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.field-card__control :deep(.el-input),
.field-card__control :deep(.el-input-number) {
  width: 100%;
}

.number-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.switch-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.field-card__unit {
  flex-shrink: 0;
  font-size: 13px;
  color: #606266;
}

.field-card__help {
  font-size: 12px;
  line-height: 1.6;
  color: #606266;
}

.field-card__note {
  font-size: 12px;
  line-height: 1.6;
  color: #909399;
}

@media (max-width: 1280px) {
  .field-grid--penalty {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .field-grid--basic,
  .field-grid--constraints,
  .field-grid--reward,
  .field-grid--penalty {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .settings-page {
    padding: 16px;
  }

  .page-header,
  .page-header__actions,
  .summary-strip {
    flex-direction: column;
    align-items: stretch;
  }

  .field-grid--basic,
  .field-grid--constraints,
  .field-grid--reward,
  .field-grid--penalty {
    grid-template-columns: 1fr;
  }

  .field-card--span-2 {
    grid-column: auto;
  }

  .field-grid,
  .section-groups,
  .section-group__header,
  .section-header {
    padding: 14px;
  }
}
</style>
