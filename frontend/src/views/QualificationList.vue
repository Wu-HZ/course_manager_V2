<template>
  <div class="page-container">
    <h2>教师资质管理</h2>

    <el-alert type="info" :closable="false" style="margin-bottom: 20px">
      这里只管理普通课程的可授课教师。校本课程由教师管理中的参与设置控制，班会由班级管理中的班主任控制。
    </el-alert>

    <el-card>
      <div class="subject-tabs">
        <span class="subject-tabs-label">选择课程：</span>
        <el-radio-group v-model="selectedSubject" @change="loadQualifications">
          <el-radio-button
            v-for="s in qualificationSubjects"
            :key="s.id"
            :value="s.id"
          >
            {{ s.name }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <div v-if="selectedSubject" class="teacher-selection">
        <div class="teacher-selection-header">
          <h4>可授课教师（勾选后自动保存）</h4>
          <div class="select-buttons">
            <el-button size="small" @click="selectAll">全选</el-button>
            <el-button size="small" @click="selectNone">全不选</el-button>
          </div>
        </div>
        <el-checkbox-group v-model="selectedTeachers" @change="saveQualifications">
          <el-checkbox
            v-for="t in teachers"
            :key="t.id"
            :label="t.id"
            :style="{ width: '150px', marginBottom: '10px' }"
          >
            {{ t.name }}
            <span v-if="t.travel_group_name" style="color: #909399; font-size: 12px">
              ({{ t.travel_group_name }})
            </span>
          </el-checkbox>
        </el-checkbox-group>
      </div>

      <el-empty v-else description="请先选择课程" />
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>资质汇总</template>
      <el-table :data="summary" stripe border>
        <el-table-column prop="subject_name" label="课程" />
        <el-table-column label="可授课教师">
          <template #default="{ row }">
            <el-tag
              v-for="t in row.teachers"
              :key="t"
              size="small"
              style="margin-right: 5px"
            >
              {{ t }}
            </el-tag>
            <span v-if="!row.teachers.length" style="color: #909399">未设置</span>
          </template>
        </el-table-column>
        <el-table-column label="教师数" width="80">
          <template #default="{ row }">
            {{ row.teachers.length }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { getSubjects } from '../api/subjects'
import { getTeachers } from '../api/teachers'

const subjects = ref([])
const teachers = ref([])
const selectedSubject = ref(null)
const selectedTeachers = ref([])
const allQualifications = ref([])
const classMeetingName = ref('班会')
let saveTimeout = null

const qualificationSubjects = computed(() => (
  subjects.value.filter(subject => (
    !subject.is_combined_class && subject.name !== classMeetingName.value
  ))
))

const summary = computed(() => {
  const teacherMap = {}
  teachers.value.forEach(t => { teacherMap[t.id] = t.name })

  return qualificationSubjects.value.map(s => {
    const teacherIds = allQualifications.value
      .filter(q => q.subject === s.id)
      .map(q => q.teacher)
    return {
      subject_id: s.id,
      subject_name: s.name,
      teachers: teacherIds.map(id => teacherMap[id] || id)
    }
  })
})

const loadData = async () => {
  const [subjectList, teacherList, qualificationList, settings] = await Promise.all([
    getSubjects(),
    getTeachers(),
    api.get('/teacher-qualifications/'),
    api.get('/scheduler-settings/'),
  ])
  subjects.value = subjectList
  teachers.value = teacherList
  allQualifications.value = qualificationList
  classMeetingName.value = settings.class_meeting_name || '班会'

  if (!qualificationSubjects.value.some(subject => subject.id === selectedSubject.value)) {
    selectedSubject.value = null
    selectedTeachers.value = []
  }
}

const loadQualifications = async () => {
  if (!selectedSubject.value) {
    selectedTeachers.value = []
    return
  }
  try {
    const res = await api.get(`/subjects/${selectedSubject.value}/qualifications/`)
    selectedTeachers.value = res.teacher_ids || []
  } catch (e) {
    selectedTeachers.value = []
    ElMessage.error(e.response?.data?.detail || '加载教师资质失败')
  }
}

const saveQualifications = () => {
  // 防抖，避免频繁保存
  if (saveTimeout) clearTimeout(saveTimeout)
  saveTimeout = setTimeout(async () => {
    try {
      await api.post(`/subjects/${selectedSubject.value}/qualifications/set/`, {
        teacher_ids: selectedTeachers.value
      })
      // 刷新汇总数据
      allQualifications.value = await api.get('/teacher-qualifications/')
      ElMessage.success('已保存')
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '保存失败')
    }
  }, 500)
}

const selectAll = () => {
  selectedTeachers.value = teachers.value.map(t => t.id)
  saveQualifications()
}

const selectNone = () => {
  selectedTeachers.value = []
  saveQualifications()
}

onMounted(loadData)
</script>

<style scoped>
.page-container { background: #fff; padding: 20px; border-radius: 4px; }
.page-container h2 { margin-bottom: 20px; }
.subject-tabs { margin-bottom: 20px; }
.subject-tabs-label { font-weight: bold; margin-right: 10px; color: #606266; }
.teacher-selection { margin-top: 20px; }
.teacher-selection-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.teacher-selection-header h4 { margin: 0; color: #606266; }
.select-buttons { display: flex; gap: 8px; }
</style>
