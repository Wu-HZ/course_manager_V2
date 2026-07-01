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

    <el-alert v-if="selectedClassId && manualAssignments.length === 0" type="warning" :closable="false" style="margin-bottom: 20px">
      该班级没有手动指定的授课分配，请先在"授课分配"页面进行手动指定。
    </el-alert>

    <el-alert v-else-if="selectedClassId" type="info" :closable="false" style="margin-bottom: 20px">
      操作说明：先在下方选中课程，再点击课表单元格填入。点击已锁定单元格可删除。
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
                    <div class="teacher">{{ getLock(day.index, period - 1).teacher_name }}</div>
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
    <div v-if="selectedClassId && manualAssignments.length > 0" class="course-panel">
      <div class="panel-header">
        <span>可用课程</span>
        <span v-if="selectedAssignment" class="selected-hint">
          已选中: {{ selectedAssignment.subject_name }} - {{ selectedAssignment.teacher_name }}
        </span>
      </div>
      <div class="course-list">
        <div
          v-for="a in manualAssignments"
          :key="a.id"
          class="course-item"
          :class="{
            'selected': selectedAssignmentId === a.id,
            'disabled': isSubjectFull(a)
          }"
          @click="selectAssignment(a)"
        >
          <div class="course-info">
            <span class="course-name">{{ a.subject_name }}</span>
            <span class="course-teacher">{{ a.teacher_name }}</span>
          </div>
          <div class="course-status">
            <span :class="{ 'full': isSubjectFull(a) }">
              {{ getLockedCount(a.subject) }}/{{ getSubjectWeeklyHours(a.subject) }}
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

const selectedAssignmentId = ref(null)  // 当前选中的课程分配

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

// 只显示手动指定的分配
const manualAssignments = computed(() => {
  return assignments.value.filter(a => a.is_manual)
})

// 统计每门课程已锁定的节数
const lockedCountBySubject = computed(() => {
  const count = {}
  for (const lock of locks.value) {
    count[lock.subject] = (count[lock.subject] || 0) + 1
  }
  return count
})

// 获取课程的周课时
const getSubjectWeeklyHours = (subjectId) => {
  const s = subjects.value.find(s => s.id === subjectId)
  return s ? s.weekly_hours : 0
}

// 获取已锁定节数
const getLockedCount = (subjectId) => {
  return lockedCountBySubject.value[subjectId] || 0
}

// 检查课程是否已达锁定上限
const isSubjectFull = (assignment) => {
  const weeklyHours = getSubjectWeeklyHours(assignment.subject)
  const locked = getLockedCount(assignment.subject)
  return locked >= weeklyHours
}

// 当前选中的分配
const selectedAssignment = computed(() => {
  return assignments.value.find(a => a.id === selectedAssignmentId.value)
})

const loadBase = async () => {
  [classes.value, subjects.value] = await Promise.all([
    api.get('/classes/'),
    api.get('/subjects/')
  ])
  // 默认选中第一个班级
  if (classes.value.length > 0) {
    selectClass(classes.value[0].id)
  }
}

const selectClass = async (classId) => {
  selectedClassId.value = classId
  selectedAssignmentId.value = null
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

// 选中课程
const selectAssignment = (assignment) => {
  if (isSubjectFull(assignment)) {
    ElMessage.warning(`${assignment.subject_name} 已达到周课时上限`)
    return
  }
  selectedAssignmentId.value = assignment.id
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
    if (!selectedAssignmentId.value) {
      ElMessage.warning('请先在下方选择一个课程')
      return
    }

    const assignment = selectedAssignment.value
    if (!assignment) return

    // 检查是否超过周课时限制
    if (isSubjectFull(assignment)) {
      ElMessage.error(`${assignment.subject_name} 已达到周课时上限`)
      return
    }

    try {
      await api.post('/schedule-locks/set/', {
        school_class: selectedClassId.value,
        day: day,
        period: period,
        subject: assignment.subject,
        teacher: assignment.teacher,
      })
      ElMessage.success('锁定成功')
      await loadLocks()
      // 如果当前选中的课程已满，清除选中状态
      if (selectedAssignment.value && isSubjectFull(selectedAssignment.value)) {
        selectedAssignmentId.value = null
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
