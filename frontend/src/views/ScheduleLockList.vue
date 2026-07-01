<template>
  <div class="page-container">
    <div class="page-header">
      <h2>课表锁定</h2>
      <el-button
        type="danger"
        @click="handleClearAll"
        :disabled="!selectedClassId || locks.length === 0"
      >
        清空本班锁定
      </el-button>
    </div>

    <!-- 班级选择 -->
    <div class="class-tabs">
      <div
        v-for="c in classes"
        :key="c.id"
        class="class-tab"
        :class="{ active: selectedClassId === c.id }"
        @click="selectClass(c.id)"
      >
        {{ c.name }}
      </div>
    </div>

    <el-alert v-if="selectedClassId && courseOptions.length === 0" type="warning" :closable="false" style="margin-bottom: 20px">
      该班级没有可锁定的课程，请先在"课程管理"中确认有适用于该班级年级的课程。
    </el-alert>

    <el-alert v-else-if="selectedClassId" type="info" :closable="false" style="margin-bottom: 20px">
      操作说明：先在下方选中课程，再点击课表单元格填入。teacher 为可选，不选则由排课时自动分配。点击已锁定单元格可删除。
    </el-alert>

    <div v-if="selectedClassId" class="lock-grid">
      <div class="lock-grid__scroll">
        <table class="lock-grid__table">
          <thead>
            <tr>
              <th class="day-col"></th>
              <th v-for="period in maxPeriods" :key="period">第{{ period }}节</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="day in days" :key="day.key">
              <td class="day-col">{{ day.label }}</td>
              <td
                v-for="period in maxPeriods"
                :key="`${day.key}-${period}`"
                :class="getCellClass(day.index, period - 1)"
                @click="handleCellClick(day.index, period - 1)"
              >
                <template v-if="isSpecialSlot(day.index, period - 1)">
                  <span class="special">{{ getSpecialLabel(day.index, period - 1) }}</span>
                </template>
                <template v-else-if="getLock(day.index, period - 1)">
                  <div class="cell-content">
                    <div class="subject">{{ getLock(day.index, period - 1).subject_name }}</div>
                    <div class="teacher">
                      {{ getLock(day.index, period - 1).teacher_name || '（教师待定）' }}
                    </div>
                  </div>
                </template>
                <template v-else>
                  <span class="empty-cell">+</span>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 可用课程列表 -->
    <div v-if="selectedClassId && courseOptions.length > 0" class="course-panel">
      <div class="panel-header">
        <span>可用课程</span>
        <span v-if="selectedCourseOption" class="selected-hint">
          已选中: {{ selectedCourseOption.subject_name }}
          <template v-if="selectedCourseOption.teacher_name"> - {{ selectedCourseOption.teacher_name }}</template>
          <template v-else>（教师待定）</template>
        </span>
      </div>
      <div class="course-list">
        <div
          v-for="co in courseOptions"
          :key="co.key"
          class="course-item"
          :class="{
            'selected': selectedCourseKey === co.key,
            'disabled': isSubjectFull(co)
          }"
          @click="selectCourse(co)"
        >
          <div class="course-info">
            <span class="course-name">{{ co.subject_name }}</span>
            <span class="course-teacher">
              <template v-if="co.teacher_name">{{ co.teacher_name }}</template>
              <template v-else>（教师待定）</template>
            </span>
          </div>
          <div class="course-status">
            <span :class="{ 'full': isSubjectFull(co) }">
              {{ getLockedCount(co.subject_id) }}/{{ co.weekly_hours }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const classes = ref([])
const subjects = ref([])  // 所有课程（包含周课时信息）
const selectedClassId = ref(null)
const locks = ref([])
const assignments = ref([])  // 该班级的所有授课分配
import { useSchoolStore } from '../stores/school'
const schoolStore = useSchoolStore()

const selectedCourseKey = ref(null)  // 当前选中的课程 key，格式 "sid" 或 "sid_tid"

const days = computed(() =>
  schoolStore.dayLabels.map((label, i) => ({ key: `d${i}`, label, index: i }))
)

const periodsPerDay = computed(() => schoolStore.periodsPerDay)
const maxPeriods = computed(() =>
  Math.max(...Object.values(schoolStore.periodsPerDay), 6)
)

// 特殊时段
const classMeetingSlot = computed(() => schoolStore.calendarConfig?.class_meeting_slot)
const combinedSlots = computed(() => schoolStore.calendarConfig?.combined_slots || [])

// 构建可锁定课程列表：该班级所有适用的普通课程，有手动分配教师则附加教师信息
const courseOptions = computed(() => {
  if (!selectedClassId.value) return []
  const cls = classes.value.find(c => c.id === selectedClassId.value)
  if (!cls) return []

  // 构建手动分配的 subject_id -> teacher 映射
  const manualMap = {}
  for (const a of assignments.value) {
    if (a.school_class === selectedClassId.value && a.is_manual) {
      manualMap[a.subject] = { id: a.id, teacher_id: a.teacher, teacher_name: a.teacher_name }
    }
  }

  const options = []
  for (const s of subjects.value) {
    // 跳过合班课和班会
    if (s.is_combined_class) continue
    // 跳过不适用年级的课程
    const grades = getApplicableGrades(s)
    if (grades.length > 0 && !grades.includes(cls.grade)) continue
    // 跳过已有关联教师身份的班会名课程
    if (s.name === classMeetingName.value) continue

    const manual = manualMap[s.id]
    const key = manual ? `${s.id}_${manual.teacher_id}` : `${s.id}`
    options.push({
      key,
      subject_id: s.id,
      subject_name: s.name,
      teacher_id: manual ? manual.teacher_id : null,
      teacher_name: manual ? manual.teacher_name : null,
      weekly_hours: s.weekly_hours,
    })
  }
  return options
})

// 统计每门课程已锁定的节数
const lockedCountBySubject = computed(() => {
  const count = {}
  for (const lock of locks.value) {
    count[lock.subject] = (count[lock.subject] || 0) + 1
  }
  return count
})

// 获取已锁定节数
const getLockedCount = (subjectId) => {
  return lockedCountBySubject.value[subjectId] || 0
}

// 检查课程是否已达锁定上限
const isSubjectFull = (co) => {
  const locked = getLockedCount(co.subject_id)
  return locked >= co.weekly_hours
}

// 当前选中的课程选项
const selectedCourseOption = computed(() => {
  return courseOptions.value.find(co => co.key === selectedCourseKey.value)
})

const loadBase = async () => {
  const [classList, subjectList, settings] = await Promise.all([
    api.get('/classes/'),
    api.get('/subjects/'),
    api.get('/scheduler-settings/'),
  ])
  classes.value = classList
  subjects.value = subjectList
  classMeetingName.value = settings.class_meeting_name || '班会'
  // 默认选中第一个班级
  if (classes.value.length > 0) {
    selectClass(classes.value[0].id)
  }
}

const selectClass = async (classId) => {
  selectedClassId.value = classId
  selectedCourseKey.value = null
  await Promise.all([loadLocks(), loadAssignments()])
}

const loadLocks = async () => {
  if (!selectedClassId.value) {
    locks.value = []
    return
  }
  locks.value = await api.get(`/classes/${selectedClassId.value}/locks/`)
}

const loadAssignments = async () => {
  if (!selectedClassId.value) {
    assignments.value = []
    return
  }
  const all = await api.get('/class-subject-teachers/')
  assignments.value = all.filter(a => a.school_class === selectedClassId.value)
}

const getLock = (day, period) => {
  return locks.value.find(l => l.day === day && l.period === period)
}

const isSpecialSlot = (day, period) => {
  const cms = classMeetingSlot.value
  if (cms && day === cms[0] && period === cms[1]) return true
  if (combinedSlots.value.some(s => s[0] === day && s[1] === period)) return true
  if (period >= (periodsPerDay.value[day] ?? 0)) return true
  return false
}

const isDisabled = (day, period) => period >= (periodsPerDay.value[day] ?? 0)

const getSpecialLabel = (day, period) => {
  const cms = classMeetingSlot.value
  if (cms && day === cms[0] && period === cms[1]) return '班会'
  if (combinedSlots.value.some(s => s[0] === day && s[1] === period)) return '校本课程'
  if (period >= (periodsPerDay.value[day] ?? 0)) return '—'
  return ''
}

const getCellClass = (day, period) => {
  if (isSpecialSlot(day, period)) return 'special-cell'
  if (getLock(day, period)) return 'has-lock'
  if (isDisabled(day, period)) return 'disabled-cell'
  if (period < 4) return 'am'
  return 'pm'
}

const getApplicableGrades = (subject) => {
  if (!subject?.applicable_grades) return []
  return String(subject.applicable_grades)
    .split(',')
    .map(item => Number(item.trim()))
    .filter(Number.isInteger)
}

// 班会名
const classMeetingName = ref('班会')

// 选中课程
const selectCourse = (co) => {
  if (isSubjectFull(co)) {
    ElMessage.warning(`${co.subject_name} 已达到周课时上限`)
    return
  }
  selectedCourseKey.value = co.key
}

// 点击单元格
const handleCellClick = async (day, period) => {
  if (isSpecialSlot(day, period)) return

  const existingLock = getLock(day, period)

  if (existingLock) {
    // 已有锁定，询问是否删除
    try {
      await ElMessageBox.confirm(
        `确定删除 ${existingLock.subject_name} 的锁定？`,
        '删除锁定',
        { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
      )
      await api.delete('/schedule-locks/delete/', {
        data: {
          school_class: selectedClassId.value,
          day: day,
          period: period,
        }
      })
      ElMessage.success('已删除锁定')
      loadLocks()
    } catch (e) {
      // 用户取消或请求失败
    }
  } else {
    // 空单元格，填入选中的课程
    if (!selectedCourseKey.value) {
      ElMessage.warning('请先在下方选择一个课程')
      return
    }

    const co = selectedCourseOption.value
    if (!co) return

    // 检查是否超过周课时限制
    if (isSubjectFull(co)) {
      ElMessage.error(`${co.subject_name} 已达到周课时上限`)
      return
    }

    try {
      const payload = {
        school_class: selectedClassId.value,
        day: day,
        period: period,
        subject: co.subject_id,
      }
      if (co.teacher_id) {
        payload.teacher = co.teacher_id
      }
      await api.post('/schedule-locks/set/', payload)
      ElMessage.success('锁定成功')
      await loadLocks()
      // 如果当前选中的课程已满，清除选中状态
      if (selectedCourseOption.value && isSubjectFull(selectedCourseOption.value)) {
        selectedCourseKey.value = null
      }
    } catch (e) {
      ElMessage.error('操作失败')
    }
  }
}

const handleClearAll = async () => {
  await ElMessageBox.confirm('确定清空该班级的所有课表锁定?', '提示', { type: 'warning' })
  try {
    for (const lock of locks.value) {
      await api.delete('/schedule-locks/delete/', {
        data: {
          school_class: selectedClassId.value,
          day: lock.day,
          period: lock.period,
        }
      })
    }
    ElMessage.success('已清空')
    loadLocks()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

onMounted(loadBase)
</script>

<style scoped>
.page-container { background: #fff; padding: 20px; border-radius: 8px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }

/* 班级标签 */
.class-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ebeef5;
}

.class-tab {
  padding: 8px 20px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
  background: #fff;
}

.class-tab:hover {
  border-color: #409eff;
  color: #409eff;
}

.class-tab.active {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
}

/* 锁定课表 - 与 TimetableGrid 一致 */
.lock-grid__scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.lock-grid__table {
  width: 100%;
  min-width: 620px;
  border-collapse: collapse;
}

.lock-grid__table th,
.lock-grid__table td {
  border: 1px solid #dcdfe6;
  padding: 8px;
  text-align: center;
  min-width: 90px;
  height: 70px;
}

.lock-grid__table th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f5f7fa;
  font-weight: bold;
}

.day-col {
  position: sticky;
  left: 0;
  z-index: 1;
  width: 60px;
  min-width: 60px !important;
  background: #f5f7fa !important;
  font-weight: bold;
}

.cell-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.subject {
  font-weight: bold;
  color: #303133;
}

.teacher {
  font-size: 12px;
  color: #909399;
}

.am { background: #f0f9eb; cursor: pointer; }
.pm { background: #fdf6ec; cursor: pointer; }
.has-lock { background: #d9ecff; cursor: pointer; }
.has-lock:hover { background: #c6e2ff; }
.special-cell { background: #f5f5f5; cursor: default; }
.special-cell:hover { background: #f5f5f5; }
.disabled-cell { background: #f5f5f5; cursor: default; }

.am:hover,
.pm:hover {
  opacity: 0.85;
  box-shadow: inset 0 0 0 2px #409eff;
}

.empty-cell { color: #c0c4cc; font-size: 20px; }
.special { color: #909399; font-size: 13px; }

/* 可用课程面板 */
.course-panel {
  margin-top: 20px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
  font-weight: bold;
}

.selected-hint {
  font-weight: normal;
  color: #409eff;
  font-size: 14px;
}

.course-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 16px;
}

.course-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border: 2px solid #dcdfe6;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 180px;
  background: #fff;
}

.course-item:hover {
  border-color: #409eff;
  background: #ecf5ff;
}

.course-item.selected {
  border-color: #409eff;
  background: #409eff;
  color: #fff;
}

.course-item.selected .course-teacher,
.course-item.selected .course-status span {
  color: rgba(255, 255, 255, 0.85);
}

.course-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: #f5f5f5;
  color: #606266;
}

.course-item.disabled .course-teacher {
  color: #909399;
}

.course-item.disabled .course-status span {
  color: #f56c6c;
}

.course-item.disabled:hover {
  border-color: #dcdfe6;
  background: #f5f5f5;
}

.course-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.course-name {
  font-weight: bold;
  font-size: 14px;
}

.course-teacher {
  font-size: 12px;
  color: #909399;
}

.course-status {
  font-size: 13px;
  color: #606266;
}

.course-status .full {
  color: #f56c6c;
}

@media (max-width: 768px) {
  .page-container {
    padding: 16px;
  }

  .lock-grid__table {
    min-width: 520px;
  }

  .lock-grid__table th,
  .lock-grid__table td {
    min-width: 72px;
    height: 64px;
    padding: 6px;
  }

  .day-col {
    width: 52px;
    min-width: 52px !important;
  }

  .subject {
    font-size: 13px;
    line-height: 1.4;
  }

  .teacher {
    font-size: 11px;
    line-height: 1.4;
  }

  .panel-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
}
</style>
