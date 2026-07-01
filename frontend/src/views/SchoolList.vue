<template>
  <div class="school-list-page">
    <div class="page-header">
      <div>
        <h1>学校管理</h1>
        <p class="page-subtitle">管理所有学校的列表，新增或修改学校信息。</p>
      </div>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon> 新增学校
      </el-button>
    </div>

    <el-card shadow="hover">
      <el-table :data="schools" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="学校名称" min-width="180" />
        <el-table-column prop="short_name" label="简称" width="120" />
        <el-table-column prop="import_key" label="导入键" min-width="260">
          <template #default="{ row }">
            <code class="import-key">{{ row.import_key }}</code>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row)">
              编辑
            </el-button>
            <el-button
              type="danger" link size="small"
              :disabled="schools.length <= 1"
              @click="confirmDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑/新增弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑学校' : '新增学校'"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="80px">
        <el-form-item label="学校名称">
          <el-input v-model="form.name" placeholder="如：某某小学" />
        </el-form-item>
        <el-form-item label="简称">
          <el-input v-model="form.short_name" placeholder="如：某某" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ isEditing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useSchoolStore } from '../stores/school'
import api from '../api'

const schoolStore = useSchoolStore()
const schools = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)
const form = ref({ name: '', short_name: '' })

const fetchList = async () => {
  loading.value = true
  try {
    schools.value = await api.get('/schools/')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  isEditing.value = false
  editingId.value = null
  form.value = { name: '', short_name: '' }
  dialogVisible.value = true
}

const openEdit = (row) => {
  isEditing.value = true
  editingId.value = row.id
  form.value = { name: row.name, short_name: row.short_name || '' }
  dialogVisible.value = true
}

const save = async () => {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入学校名称')
    return
  }
  saving.value = true
  try {
    if (isEditing.value) {
      await api.patch(`/schools/${editingId.value}/`, form.value)
      ElMessage.success('学校信息已更新')
    } else {
      await api.post('/schools/', form.value)
      ElMessage.success('学校已创建')
    }
    dialogVisible.value = false
    await fetchList()
    await schoolStore.fetchSchools()
  } catch (e) {
    ElMessage.error('操作失败')
  } finally {
    saving.value = false
  }
}

const confirmDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除学校"${row.short_name || row.name}"吗？该校所有数据（教师、班级、课程、课表等）将被一并删除，不可恢复。`,
      '确认删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.delete(`/schools/${row.id}/`)
    ElMessage.success('学校已删除')
    await fetchList()
    await schoolStore.fetchSchools()
  } catch {
    // 取消
  }
}

onMounted(fetchList)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 4px;
}

.page-subtitle {
  color: #909399;
  font-size: 13px;
}

.import-key {
  font-size: 12px;
  background: #f4f5f7;
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}
</style>
