<template>
  <div class="page-container">
    <div class="page-header">
      <h2>送教分组管理</h2>
      <el-button type="primary" @click="showDialog()">
        <el-icon><Plus /></el-icon> 添加分组
      </el-button>
    </div>

    <el-table :data="groups" stripe border>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="分组名称" />
      <el-table-column prop="day_off_display" label="禁排日" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button size="small" @click="showDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑分组' : '添加分组'" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="分组名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="禁排日" required>
          <el-select v-model="form.day_off">
            <el-option
              v-for="d in schoolStore.dayOptions"
              :key="d.value"
              :label="d.label"
              :value="d.value"
            />
          </el-select>
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
import { getTravelGroups, createTravelGroup, updateTravelGroup, deleteTravelGroup } from '../api/resources'
import { useSchoolStore } from '../stores/school'

const schoolStore = useSchoolStore()

const groups = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({ name: '', day_off: 0 })

const loadData = async () => {
  groups.value = await getTravelGroups()
}

const showDialog = (row = null) => {
  if (row) {
    editingId.value = row.id
    form.value = { name: row.name, day_off: row.day_off }
  } else {
    editingId.value = null
    form.value = { name: '', day_off: 0 }
  }
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    if (editingId.value) {
      await updateTravelGroup(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createTravelGroup(form.value)
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
    await deleteTravelGroup(row.id)
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
