<template>
  <div class="page-container">
    <div class="page-header">
      <h2>校本课程分组</h2>
      <el-button type="primary" @click="showDialog()">
        <el-icon><Plus /></el-icon> 添加分组
      </el-button>
    </div>

    <el-alert type="info" :closable="false" style="margin-bottom: 20px">
      <p>校本课程需要4个分组，每个分组对应一位教师。</p>
      <p>教师分配规则：手动指定 > 自动分配（未指定且未排除的教师随机分配）</p>
    </el-alert>

    <el-table :data="groups" stripe border>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="分组名称" />
      <el-table-column prop="teacher_count" label="已分配教师数" width="120" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button size="small" @click="showDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑分组' : '添加分组'" width="400px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="分组名称" required>
          <el-input v-model="form.name" placeholder="如：第1组、书法组" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const groups = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({ name: '' })

const loadData = async () => {
  groups.value = await api.get('/combined-class-groups/')
}

const showDialog = (row = null) => {
  if (row) {
    editingId.value = row.id
    form.value = { name: row.name }
  } else {
    editingId.value = null
    form.value = { name: '' }
  }
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入分组名称')
    return
  }
  try {
    if (editingId.value) {
      await api.put(`/combined-class-groups/${editingId.value}/`, form.value)
      ElMessage.success('更新成功')
    } else {
      await api.post('/combined-class-groups/', form.value)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm('确定删除该分组?', '提示', { type: 'warning' })
  try {
    await api.delete(`/combined-class-groups/${row.id}/`)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.page-container { background: #fff; padding: 20px; border-radius: 4px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
</style>
