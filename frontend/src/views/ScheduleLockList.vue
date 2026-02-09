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
        <span>点击单元格锁定课程时间：</span>
        <span class="legend-item"><span class="cell-demo locked"></span> 已锁定</span>
        <span class="legend-item"><span class="cell-demo special"></span> 特殊时段（不可编辑）</span>
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

    <!-- 锁定设置弹窗 -->
    <el-dialog v-model="dialogVisible" title="设置课表锁定" width="400px">
      <el-form label-width="80px">
        <el-form-item label="时间">
          {{ dayNames[editDay] }} 第{{ editPeriod + 1 }}节
        </el-form-item>
        <el-form-item label="课程" required>
          <el-select v-model="editAssignmentId" placeholder="选择已分配的课程" style="width: 100%;" @change="onAssignmentChange">
            <el-option
              v-for="a in manualAssignments"
              :key="a.id"
              :label="getAssignmentLabel(a)"
              :value="a.id"
              :disabled="isSubjectFull(a)"
            />
          </el-select>
          <div v-if="manualAssignments.length === 0" style="color: #f56c6c; font-size: 12px; margin-top: 5px">
            没有手动指定的授课分配
          </div>
        </el-form-item>
        <el-form-item label="教师" v-if="selectedAssignment">
          <el-input :value="selectedAssignment.teacher_name" disabled />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button v-if="hasExistingLock" type="danger" @click="handleDeleteLock">删除锁定</el-button>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveLock" :disabled="!editAssignmentId">确定</el-button>
      </template>
    </el-dialog>
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

const dayNames = ['周一', '周二', '周三', '周四', '周五']
const periodsPerDay = { 0: 6, 1: 6, 2: 6, 3: 6, 4: 4 }
const maxPeriods = 6

// 特殊时段
const fridayClassMeeting = { day: 4, period: 3 }
const combinedSlots = [
  { day: 1, period: 4 }, { day: 1, period: 5 },
  { day: 3, period: 4 }, { day: 3, period: 5 }
]

// 弹窗状态
const dialogVisible = ref(false)
const editDay = ref(0)
const editPeriod = ref(0)
const editAssignmentId = ref(null)
const hasExistingLock = ref(false)

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

// 获取课程剩余可锁定节数
const getRemainingSlots = (subjectId) => {
  const weeklyHours = getSubjectWeeklyHours(subjectId)
  const locked = lockedCountBySubject.value[subjectId] || 0
  return weeklyHours - locked
}

// 检查课程是否已达锁定上限（考虑当前正在编辑的锁定）
const isSubjectFull = (assignment) => {
  const remaining = getRemainingSlots(assignment.subject)
  // 如果正在编辑已有锁定，且选的是同一门课，不算满
  if (hasExistingLock.value) {
    const existingLock = getLock(editDay.value, editPeriod.value)
    if (existingLock && existingLock.subject === assignment.subject) {
      return remaining < 0  // 已有锁定占用了一个位置，所以允许
    }
  }
  return remaining <= 0
}

// 生成下拉选项标签，显示剩余可锁定节数
const getAssignmentLabel = (assignment) => {
  const weeklyHours = getSubjectWeeklyHours(assignment.subject)
  const locked = lockedCountBySubject.value[assignment.subject] || 0
  const remaining = weeklyHours - locked

  // 如果正在编辑已有锁定，且选的是同一门课，剩余数+1
  let displayRemaining = remaining
  if (hasExistingLock.value) {
    const existingLock = getLock(editDay.value, editPeriod.value)
    if (existingLock && existingLock.subject === assignment.subject) {
      displayRemaining = remaining + 1
    }
  }

  return `${assignment.subject_name} - ${assignment.teacher_name} (${locked}/${weeklyHours}，剩余${displayRemaining}节)`
}

// 当前选中的分配
const selectedAssignment = computed(() => {
  return assignments.value.find(a => a.id === editAssignmentId.value)
})

const loadBase = async () => {
  [classes.value, subjects.value] = await Promise.all([
    api.get('/classes/'),
    api.get('/subjects/')
  ])
}

const onClassChange = async () => {
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
  // 获取该班级的授课分配
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

const handleCellClick = (day, period) => {
  if (isSpecialSlot(day, period)) return
  if (manualAssignments.value.length === 0) {
    ElMessage.warning('请先在"授课分配"页面进行手动指定')
    return
  }

  const existing = getLock(day, period)
  editDay.value = day
  editPeriod.value = period

  if (existing) {
    // 找到对应的分配
    const matchingAssignment = assignments.value.find(
      a => a.subject === existing.subject && a.teacher === existing.teacher
    )
    editAssignmentId.value = matchingAssignment?.id || null
    hasExistingLock.value = true
  } else {
    editAssignmentId.value = null
    hasExistingLock.value = false
  }
  dialogVisible.value = true
}

const onAssignmentChange = () => {
  // 选择分配后自动填充教师信息
}

const handleSaveLock = async () => {
  if (!editAssignmentId.value) {
    ElMessage.warning('请选择课程')
    return
  }
  const assignment = selectedAssignment.value
  if (!assignment) return

  // 检查是否超过周课时限制
  const weeklyHours = getSubjectWeeklyHours(assignment.subject)
  const currentLocked = lockedCountBySubject.value[assignment.subject] || 0

  // 如果不是编辑同一门课的锁定，需要检查是否超限
  const existingLock = getLock(editDay.value, editPeriod.value)
  const isSameSubject = existingLock && existingLock.subject === assignment.subject

  if (!isSameSubject && currentLocked >= weeklyHours) {
    ElMessage.error(`${assignment.subject_name} 已锁定 ${currentLocked} 节，达到周课时上限 ${weeklyHours} 节`)
    return
  }

  try {
    await api.post('/schedule-locks/set/', {
      school_class: selectedClassId.value,
      day: editDay.value,
      period: editPeriod.value,
      subject: assignment.subject,
      teacher: assignment.teacher,
    })
    ElMessage.success('锁定成功')
    dialogVisible.value = false
    loadLocks()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleDeleteLock = async () => {
  try {
    await api.delete('/schedule-locks/delete/', {
      data: {
        school_class: selectedClassId.value,
        day: editDay.value,
        period: editPeriod.value,
      }
    })
    ElMessage.success('已取消锁定')
    dialogVisible.value = false
    loadLocks()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleClearAll = async () => {
  await ElMessageBox.confirm('确定清空该班级的所有课表锁定?', '提示', { type: 'warning' })
  try {
    // 逐个删除该班级的锁定
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

.legend {
  display: flex;
  align-items: center;
  gap: 20px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}
.cell-demo {
  display: inline-block;
  width: 20px;
  height: 20px;
  border-radius: 3px;
  border: 1px solid #dcdfe6;
}
.cell-demo.locked { background: #d9ecff; }
.cell-demo.special { background: #f0f0f0; }

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
</style>
