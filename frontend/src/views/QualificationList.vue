<template>
  <div class="page-container">
    <div class="page-header">
      <h2>教师资质管理</h2>
    </div>

    <el-alert type="info" :closable="false" style="margin-bottom: 20px">
      勾选后自动保存。校本课程由教师管理中的参与设置控制，班会由班级管理中的班主任控制。
    </el-alert>

    <div v-if="qualificationSubjects.length && teachers.length" class="qual-grid">
      <div class="qual-grid__scroll">
        <table class="qual-grid__table">
          <thead>
            <tr>
              <th class="teacher-head-col">教师</th>
              <th
                v-for="s in qualificationSubjects"
                :key="s.id"
                class="subject-head-col"
              >
                <div class="subject-head__name">{{ s.name }}</div>
                <div class="subject-head__count">
                  {{ subjectCount(s.id) }}/{{ teachers.length }}
                </div>
              </th>
              <th class="action-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in teachers" :key="t.id">
              <td class="teacher-head-col">{{ t.name }}</td>
              <td
                v-for="s in qualificationSubjects"
                :key="`${t.id}-${s.id}`"
                class="check-col"
                :class="{ 'col-checked': isChecked(s.id, t.id) }"
                @click="toggle(s.id, t.id)"
              >
                <el-icon v-if="isChecked(s.id, t.id)" class="check-icon" color="#409eff"><Check /></el-icon>
              </td>
              <td class="action-col">
                <div class="action-btns">
                  <el-button size="small" text type="primary" @click="selectAllForTeacher(t.id)">全选</el-button>
                  <el-button size="small" text type="warning" @click="selectNoneForTeacher(t.id)">清空</el-button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <el-empty v-else description="请先添加课程和教师数据" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Check } from '@element-plus/icons-vue'
import api from '../api'
import { getSubjects } from '../api/subjects'
import { getTeachers } from '../api/teachers'

const subjects = ref([])
const teachers = ref([])
const classMeetingName = ref('班会')
// `${subjectId}-${teacherId}` → true
const checked = reactive({})
// 防抖定时器: subjectId → timeoutId
const saveTimers = {}

// 只对普通课程管理资质
const qualificationSubjects = computed(() =>
  subjects.value.filter(s => !s.is_combined_class && s.name !== classMeetingName.value)
)

const isChecked = (subjectId, teacherId) => !!checked[`${subjectId}-${teacherId}`]

const subjectCount = (subjectId) => {
  let n = 0
  for (const t of teachers.value) {
    if (checked[`${subjectId}-${t.id}`]) n++
  }
  return n
}

const collectTeacherIds = (subjectId) =>
  teachers.value.filter(t => checked[`${subjectId}-${t.id}`]).map(t => t.id)

const saveSubject = async (subjectId) => {
  try {
    await api.post(`/subjects/${subjectId}/qualifications/set/`, {
      teacher_ids: collectTeacherIds(subjectId)
    })
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

const debouncedSave = (subjectId) => {
  if (saveTimers[subjectId]) clearTimeout(saveTimers[subjectId])
  saveTimers[subjectId] = setTimeout(() => {
    delete saveTimers[subjectId]
    saveSubject(subjectId)
  }, 400)
}

const toggle = (subjectId, teacherId) => {
  const key = `${subjectId}-${teacherId}`
  if (checked[key]) {
    delete checked[key]
  } else {
    checked[key] = true
  }
  debouncedSave(subjectId)
}

const setTeacherForSubjects = (teacherId, subjectIds, add) => {
  for (const sid of subjectIds) {
    const key = `${sid}-${teacherId}`
    if (add) {
      checked[key] = true
    } else {
      delete checked[key]
    }
    debouncedSave(sid)
  }
}

const selectAllForTeacher = (teacherId) => {
  setTeacherForSubjects(teacherId, qualificationSubjects.value.map(s => s.id), true)
}

const selectNoneForTeacher = (teacherId) => {
  setTeacherForSubjects(teacherId, qualificationSubjects.value.map(s => s.id), false)
}

const loadData = async () => {
  const [subjectList, teacherList, qualificationList, settings] = await Promise.all([
    getSubjects(),
    getTeachers(),
    api.get('/teacher-qualifications/'),
    api.get('/scheduler-settings/'),
  ])
  subjects.value = subjectList
  teachers.value = teacherList
  classMeetingName.value = settings.class_meeting_name || '班会'

  for (const key of Object.keys(checked)) delete checked[key]
  for (const q of qualificationList) {
    checked[`${q.subject}-${q.teacher}`] = true
  }
}

onMounted(loadData)
</script>

<style scoped>
.page-container { background: #fff; padding: 20px; border-radius: 8px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }

/* ---------- 网格 ---------- */
.qual-grid__scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.qual-grid__table {
  width: 100%;
  min-width: 700px;
  border-collapse: collapse;
}

.qual-grid__table th,
.qual-grid__table td {
  border: 1px solid #ebeef5;
  padding: 6px 8px;
  text-align: center;
  height: 44px;
  white-space: nowrap;
}

.qual-grid__table th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f5f7fa;
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}

/* 教师首列 (sticky left) */
.teacher-head-col {
  position: sticky;
  left: 0;
  z-index: 1;
  background: #fafafa !important;
  min-width: 70px;
  text-align: left !important;
  padding-left: 12px !important;
  font-size: 13px;
  font-weight: 600;
}

/* 课程列表头 */
.subject-head-col {
  min-width: 82px;
  width: 82px;
  line-height: 1.3;
  vertical-align: bottom;
}

.subject-head__name {
  font-size: 13px;
}

.subject-head__count {
  font-size: 11px;
  font-weight: 400;
  color: #909399;
  margin-top: 2px;
}

/* 勾选列 */
.check-col {
  cursor: pointer;
  transition: background 0.15s;
}

.check-col:hover {
  background: #ecf5ff;
}

.col-checked {
  background: #ecf5ff;
}

.check-icon {
  font-size: 18px;
}

/* 操作列 (sticky right) */
.action-col {
  position: sticky;
  right: 0;
  z-index: 1;
  background: #fff !important;
  min-width: 110px;
  width: 110px;
}

.qual-grid__table thead .action-col {
  background: #f5f7fa !important;
}

.action-btns {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: center;
}

.action-btns .el-button {
  padding: 2px 6px;
  font-size: 12px;
}

@media (max-width: 768px) {
  .page-container { padding: 16px; }

  .qual-grid__table { min-width: 560px; }

  .subject-head-col { min-width: 72px; width: 72px; }

  .teacher-head-col { min-width: 64px; padding-left: 10px !important; }

  .action-col { min-width: 96px; width: 96px; }
}
</style>
