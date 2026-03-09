<template>
  <div class="dashboard">
    <h1>自动排课系统</h1>
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>教师数量</template>
          <div class="stat-number">{{ stats.teachers }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>班级数量</template>
          <div class="stat-number">{{ stats.classes }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>课程数量</template>
          <div class="stat-number">{{ stats.subjects }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>授课分配</template>
          <div class="stat-number">{{ stats.assignments }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="quick-actions" shadow="hover">
      <template #header>快速操作</template>
      <el-space>
        <el-button type="primary" @click="$router.push('/schedule-run')">
          <el-icon><VideoPlay /></el-icon> 执行排课
        </el-button>
        <el-button @click="$router.push('/schedule-view')">
          <el-icon><Calendar /></el-icon> 查看课表
        </el-button>
      </el-space>
    </el-card>

    <el-card class="data-io" shadow="hover">
      <template #header>数据导入导出</template>
      <el-space>
        <el-button type="success" @click="handleExport" :loading="exporting">
          <el-icon><Download /></el-icon> 导出Excel
        </el-button>
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx,.xls"
          :on-change="handleImport"
        >
          <el-button type="warning" :loading="importing">
            <el-icon><Upload /></el-icon> 导入Excel
          </el-button>
        </el-upload>
      </el-space>
      <div class="io-tips">
        <el-text type="info" size="small">
          导出包含：送教分组、校本课程分组、场地、课程、教师、班级、教师资质、授课分配
        </el-text>
      </div>
    </el-card>

    <!-- 导入结果对话框 -->
    <el-dialog v-model="importResultVisible" title="导入结果" width="500px">
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
        <div v-if="importResult.error_count > 0" style="margin-top: 15px">
          <el-alert type="warning" :closable="false">
            <template #title>
              共 {{ importResult.error_count }} 条错误
            </template>
            <div style="max-height: 200px; overflow-y: auto; margin-top: 10px">
              <div v-for="(err, idx) in importResult.errors" :key="idx" style="font-size: 12px">
                {{ err }}
              </div>
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
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getTeachers } from '../api/teachers'
import { getClasses } from '../api/classes'
import { getSubjects } from '../api/subjects'
import { getAssignments } from '../api/resources'
import axios from 'axios'

const stats = ref({
  teachers: 0,
  classes: 0,
  subjects: 0,
  assignments: 0
})

const exporting = ref(false)
const importing = ref(false)
const importResultVisible = ref(false)
const importResult = ref(null)

const loadStats = async () => {
  try {
    const [teachers, classes, subjects, assignments] = await Promise.all([
      getTeachers(),
      getClasses(),
      getSubjects(),
      getAssignments()
    ])
    stats.value = {
      teachers: teachers.length,
      classes: classes.length,
      subjects: subjects.length,
      assignments: assignments.length
    }
  } catch (e) {
    console.error('Failed to load stats:', e)
  }
}

const handleExport = async () => {
  exporting.value = true
  try {
    const response = await axios.get('/api/data/export/', {
      responseType: 'blob'
    })
    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'course_manager_data.xlsx')
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败')
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
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    importResult.value = response.data
    importResultVisible.value = true
    // 刷新统计
    loadStats()
    ElMessage.success('导入完成')
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '导入失败')
  } finally {
    importing.value = false
  }
}

onMounted(loadStats)
</script>

<style scoped>
.dashboard h1 {
  margin-bottom: 20px;
  color: #303133;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-number {
  font-size: 36px;
  font-weight: bold;
  color: #409EFF;
  text-align: center;
}

.quick-actions {
  margin-top: 20px;
}

.data-io {
  margin-top: 20px;
}

.io-tips {
  margin-top: 12px;
}
</style>
