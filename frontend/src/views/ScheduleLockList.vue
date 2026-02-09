<template>
  <div class="page-container">
    <div class="page-header">
      <h2>课表锁定</h2>
      <div style="display: flex; align-items: center; gap: 10px;">
        <el-select v-model="selectedClassId" placeholder="选择班级" @change="onClassChange" style="width: 200px;">
          <el-option
            v-for="c in classes"
            :key="c.id"
            :label="c.name"
            :value="c.id"
          />
        </el-select>
        <el-button type="danger" @click="handleClearAll" :disabled="!selectedClassId || locks.length === 0">
          清空本班锁定
        </el-button>
      </div>
    </div>

    <el-alert v-if="selectedClassId && manualAssignments.length === 0" type="warning" :closable="false" style="margin-bottom: 20px">
      该班级没有手动指定的授课分配，请先在"授课分配"页面进行手动指定。
    </el-alert>

    <el-alert v-else-if="selectedClassId" type="info" :closable="false" style="margin-bottom: 20px">
      <div class="legend">
        <span>操作说明：先在下方选中课程，再点击课表单元格填入。点击已锁定单元格可删除。</span>
      </div>
    </el-alert>

    <div v-if="selectedClassId" class="schedule-grid">
      <table border="1" cellspacing="0">
        <thead>
          <tr>
            <th class="period-col">节次</th>
            <th v-for="(dayName, dayIdx) in dayNames" :key="dayIdx" class="day-col">{{ dayName }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="period in maxPeriods" :key="period">
            <td class="period-col">第{{ period }}节</td>
            <td
              v-for="(dayName, dayIdx) in dayNames"
              :key="dayIdx"
              class="cell"
              :class="getCellClass(dayIdx, period - 1)"
              @click="handleCellClick(dayIdx, period - 1)"
            >
              <template v-if="isSpecialSlot(dayIdx, period - 1)">
                <span class="special">{{ getSpecialLabel(dayIdx, period - 1) }}</span>
              </template>
              <template v-else-if="getLock(dayIdx, period - 1)">
                <div class="locked-cell">
                  <div class="subject-name">{{ getLock(dayIdx, period - 1).subject_name }}</div>
                  <div class="teacher-name">{{ getLock(dayIdx, period - 1).teacher_name }}</div>
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
    <div v-else class="empty-tip">
      请先选择一个班级
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
const selectedAssignmentId = ref(null)  // 当前选中的课程分配

const dayNames = ['周一', '周二', '周三', '周四', '周五']
const maxPeriods = 6

// 特殊时段
const fridayClassMeeting = { day: 4, period: 3 }
const combinedSlots = [
  { day: 1, period: 4 }, { day: 1, period: 5 },
  { day: 3, period: 4 }, { day: 3, period: 5 }
]

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
}

const onClassChange = async () => {
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
  if (day === fridayClassMeeting.day && period === fridayClassMeeting.period) return true
  if (combinedSlots.some(s => s.day === day && s.period === period)) return true
  if (day === 4 && period >= 4) return true
  return false
}

const getSpecialLabel = (day, period) => {
  if (day === fridayClassMeeting.day && period === fridayClassMeeting.period) return '班会'
  if (combinedSlots.some(s => s.day === day && s.period === period)) return '校本课程'
  if (day === 4 && period >= 4) return '-'
  return ''
}

const getCellClass = (day, period) => {
  if (isSpecialSlot(day, period)) return 'special-cell'
  if (getLock(day, period)) return 'has-lock'
  return ''
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
      loadLocks()
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
.page-container { background: #fff; padding: 20px; border-radius: 4px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }

.schedule-grid { overflow-x: auto; }
.schedule-grid table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.schedule-grid th, .schedule-grid td {
  padding: 8px;
  text-align: center;
  border: 1px solid #dcdfe6;
  height: 60px;
}
.schedule-grid th { background: #f5f7fa; font-weight: bold; }

.period-col { width: 70px; background: #f5f7fa; font-weight: bold; }
.day-col { width: 18%; }

.cell { cursor: pointer; transition: background 0.2s; }
.cell:hover { background: #ecf5ff; }

.special-cell {
  background: #f0f0f0;
  color: #909399;
  cursor: default;
}
.special-cell:hover { background: #f0f0f0; }

.has-lock { background: #d9ecff; }
.has-lock:hover { background: #c6e2ff; }

.locked-cell .subject-name { font-weight: bold; color: #409eff; font-size: 14px; }
.locked-cell .teacher-name { color: #909399; font-size: 12px; margin-top: 2px; }

.empty-cell { color: #dcdfe6; font-size: 20px; }
.special { color: #909399; font-size: 12px; }

.empty-tip { text-align: center; color: #909399; padding: 60px 0; font-size: 16px; }

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
</style>
