<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <div>
        <h1>智能排课系统</h1>
        <p class="page-subtitle">先完成基础数据和关键约束，再开始试排和查看结果。</p>
      </div>
      <el-space wrap>
        <el-button type="primary" @click="router.push('/schedule-run')">
          <el-icon><VideoPlay /></el-icon> 执行排课
        </el-button>
        <el-button @click="router.push('/schedule-view')">
          <el-icon><Calendar /></el-icon> 查看课表
        </el-button>
      </el-space>
    </div>

    <el-row v-if="precheck" :gutter="20" class="stats-row">
      <el-col :xs="12" :lg="4">
        <el-card class="stats-card" shadow="hover">
          <template #header>教师数量</template>
          <div class="stat-number">{{ stats.teachers }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="4">
        <el-card class="stats-card" shadow="hover">
          <template #header>班级数量</template>
          <div class="stat-number">{{ stats.classes }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="4">
        <el-card class="stats-card" shadow="hover">
          <template #header>课程数量</template>
          <div class="stat-number">{{ stats.subjects }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="4">
        <el-card class="stats-card" shadow="hover">
          <template #header>授课分配</template>
          <div class="stat-number">{{ stats.assignments }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="4">
        <el-card class="stats-card" shadow="hover">
          <template #header>校课时量</template>
          <div class="stat-number">{{ stats.totalSchoolHours }}</div>
          <div class="stat-caption">含校本课程、班会课</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="4">
        <el-card class="stats-card" shadow="hover">
          <template #header>人均课时</template>
          <div class="stat-number">{{ averageTeacherHoursDisplay }}</div>
          <div class="stat-caption">按全校总课时 / 教师数</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row v-if="precheck" :gutter="20" class="guide-row">
      <el-col :xs="24" :lg="16">
        <PreparationFlowCard :precheck="precheck" />
      </el-col>
      <el-col :xs="24" :lg="8">
        <el-card class="todo-card" shadow="hover">
          <template #header>当前待办</template>

          <template v-if="pendingIssues.length">
            <div class="todo-headline" :class="todoToneClass">{{ todoHeadline }}</div>
            <div class="todo-description">{{ todoDescription }}</div>

            <div class="todo-list">
              <div v-for="issue in pendingIssues" :key="issue.key" class="todo-item">
                <div class="todo-item-title">{{ issue.title }}</div>
                <div class="todo-item-detail">{{ issue.detail }}</div>
              </div>
            </div>

            <div class="todo-actions">
              <el-button
                v-for="action in todoActions"
                :key="action.route"
                :type="precheck.blocking_issues.length ? 'danger' : 'primary'"
                plain
                @click="router.push(action.route)"
              >
                {{ action.label }}
              </el-button>
            </div>
          </template>

          <template v-else>
            <div class="todo-headline success">基础检查已通过</div>
            <div class="todo-description">当前数据可以开始排课，也可以继续微调约束后再试排。</div>
            <div class="todo-actions">
              <el-button type="primary" @click="router.push('/schedule-run')">去执行排课</el-button>
              <el-button @click="router.push('/schedule-view')">查看课表</el-button>
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="data-io" shadow="hover">
      <template #header>数据导入导出</template>
      <el-space wrap>
        <el-button type="success" @click="handleExport" :loading="exporting">
          <el-icon><Download /></el-icon> 导出 Excel
        </el-button>
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx,.xls"
          :on-change="handleImport"
        >
          <el-button type="warning" :loading="importing">
            <el-icon><Upload /></el-icon> 导入 Excel
          </el-button>
        </el-upload>
      </el-space>
      <div class="io-tips">
        <el-text type="info" size="small">
          导入导出包含：送教分组、校本课程分组、场地、课程、教师、班级、教师资质和授课分配。
        </el-text>
      </div>
    </el-card>

    <el-dialog v-model="importResultVisible" title="导入结果" width="560px">
      <div v-if="importResult">
        <el-descriptions :column="2" border>
          <el-descriptions-item
            v-for="(value, key) in importResult.results"
            :key="key"
            :label="key"
          >
            新增 {{ value.created }}，更新 {{ value.updated }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="importResult.error_count > 0" class="import-errors">
          <el-alert :type="importResult.committed === false ? 'error' : 'warning'" :closable="false">
            <template #title>
              {{
                importResult.committed === false
                  ? `共有 ${importResult.error_count} 条导入问题，本次已回滚，未写入任何数据`
                  : `共有 ${importResult.error_count} 条导入提示`
              }}
            </template>
            <div class="import-error-list">
              <div v-for="(err, idx) in importResult.errors" :key="idx">{{ err }}</div>
            </div>
          </el-alert>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="importResultVisible = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import PreparationFlowCard from '../components/PreparationFlowCard.vue'
import { getSchedulePrecheck } from '../api/scheduler'

const router = useRouter()

const precheck = ref(null)
const exporting = ref(false)
const importing = ref(false)
const importResultVisible = ref(false)
const importResult = ref(null)

const stats = computed(() => ({
  teachers: precheck.value?.summary.teachers_count || 0,
  classes: precheck.value?.summary.classes_count || 0,
  subjects: precheck.value?.summary.subjects_count || 0,
  assignments: precheck.value?.summary.assignments_count || 0,
  totalSchoolHours: precheck.value?.summary.total_school_hours || 0,
}))

const averageTeacherHoursDisplay = computed(() => {
  const value = precheck.value?.summary.average_teacher_hours
  if (value == null) {
    return '--'
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
})

const pendingIssues = computed(() => {
  if (!precheck.value) {
    return []
  }
  if (precheck.value.blocking_issues.length > 0) {
    return precheck.value.blocking_issues
  }
  return precheck.value.warning_issues.slice(0, 3)
})

const todoHeadline = computed(() => {
  if (!precheck.value) {
    return '正在加载准备状态'
  }
  if (precheck.value.blocking_issues.length > 0) {
    return `还需处理 ${precheck.value.summary.blocking_issue_count} 项，暂时不能开始排课`
  }
  if (precheck.value.warning_issues.length > 0) {
    return `可以开始试排，另有 ${precheck.value.summary.warning_issue_count} 项建议优化`
  }
  return '基础检查已通过'
})

const todoDescription = computed(() => {
  if (!precheck.value) {
    return ''
  }
  if (precheck.value.blocking_issues.length > 0) {
    return '请优先处理以下必须项，处理完成后即可进入执行排课。'
  }
  if (precheck.value.warning_issues.length > 0) {
    return '当前已经具备试排条件，以下项目不影响排课，但建议在试排前补充。'
  }
  return '当前数据可以开始排课，也可以继续微调约束后再试排。'
})

const todoToneClass = computed(() => {
  if (!precheck.value) {
    return ''
  }
  if (precheck.value.blocking_issues.length > 0) {
    return 'danger'
  }
  if (precheck.value.warning_issues.length > 0) {
    return 'warning'
  }
  return 'success'
})

const todoActions = computed(() => {
  if (!precheck.value) {
    return []
  }
  if (precheck.value.blocking_issues.length > 0) {
    return precheck.value.blocking_issues[0]?.actions || []
  }
  if (precheck.value.warning_issues.length > 0) {
    return precheck.value.warning_issues[0]?.actions || []
  }
  return [
    { label: '去执行排课', route: '/schedule-run' },
    { label: '查看课表', route: '/schedule-view' },
  ]
})

const loadDashboardData = async () => {
  try {
    precheck.value = await getSchedulePrecheck()
  } catch (error) {
    console.error('Failed to load dashboard precheck:', error)
  }
}

const parseBlobErrorPayload = async (blob) => {
  if (!(blob instanceof Blob)) {
    return blob || null
  }

  const text = await blob.text()
  if (!text) {
    return null
  }

  try {
    return JSON.parse(text)
  } catch {
    return { error: text }
  }
}

const handleExport = async () => {
  exporting.value = true
  try {
    const response = await axios.get('/api/data/export/', {
      responseType: 'blob',
    })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'course_manager_data.xlsx')
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    const responseData = await parseBlobErrorPayload(error.response?.data)
    if (responseData?.errors?.length) {
      await ElMessageBox.alert(
        h(
          'div',
          { style: 'white-space: pre-line;' },
          responseData.errors.join('\n')
        ),
        responseData.error || '导出失败',
        {
          type: 'error',
          confirmButtonText: '确定',
        }
      )
    } else {
      ElMessage.error(responseData?.error || '导出失败')
    }
  } finally {
    exporting.value = false
  }
}

const handleImport = async (file) => {
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', file.raw)
    const response = await axios.post('/api/data/import/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    importResult.value = response.data
    importResultVisible.value = true
    await loadDashboardData()
    ElMessage.success('导入完成')
  } catch (error) {
    const responseData = error.response?.data
    if (responseData?.results) {
      importResult.value = responseData
      importResultVisible.value = true
    }
    ElMessage.error(responseData?.error || '导入失败')
  } finally {
    importing.value = false
  }
}

onMounted(loadDashboardData)
</script>

<style scoped>
.dashboard-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 20px;
}

.dashboard h1 {
  margin: 0;
  color: #303133;
}

.page-subtitle {
  margin: 8px 0 0;
  font-size: 14px;
  line-height: 1.7;
  color: #606266;
}

.guide-row,
.stats-row {
  margin-bottom: 20px;
}

.stats-row :deep(.el-col) {
  display: flex;
}

.stats-card {
  width: 100%;
}

.stats-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 112px;
}

.todo-card {
  height: 100%;
}

.todo-headline {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.todo-headline.danger {
  color: #f56c6c;
}

.todo-headline.warning {
  color: #e6a23c;
}

.todo-headline.success {
  color: #67c23a;
}

.todo-description {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.7;
  color: #606266;
}

.todo-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.todo-item {
  padding: 12px 14px;
  border-radius: 10px;
  background: #f5f7fa;
}

.todo-item-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.todo-item-detail {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: #606266;
}

.todo-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.stat-number {
  font-size: 36px;
  font-weight: 700;
  color: #409eff;
  text-align: center;
}

.stat-caption {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.5;
  text-align: center;
  color: #909399;
}

.data-io {
  margin-top: 20px;
}

.io-tips {
  margin-top: 12px;
}

.import-errors {
  margin-top: 15px;
}

.import-error-list {
  max-height: 220px;
  overflow-y: auto;
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 768px) {
  .dashboard-header {
    flex-direction: column;
  }
}
</style>
