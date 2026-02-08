<template>
  <div class="page-container">
    <div class="page-header">
      <h2>教师管理</h2>
      <el-button type="primary" @click="showDialog()">
        <el-icon><Plus /></el-icon> 添加教师
      </el-button>
    </div>

    <el-table :data="teachers" stripe border>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="travel_group_name" label="出差分组" />
      <el-table-column label="校本课程" width="140">
        <template #default="{ row }">
          <el-tag v-if="row.exclude_from_combined" type="info">不参与</el-tag>
          <span v-else-if="row.combined_class_group_name">{{ row.combined_class_group_name }}</span>
          <span v-else style="color: #909399">自动分配</span>
        </template>
      </el-table-column>
      <el-table-column label="周课时" width="150">
        <template #default="{ row }">
          <span v-if="row.min_weekly_hours != null && row.max_weekly_hours != null">
            {{ row.min_weekly_hours }}~{{ row.max_weekly_hours }} 节
          </span>
          <span v-else-if="row.max_weekly_hours != null">
            上限 {{ row.max_weekly_hours }} 节
          </span>
          <span v-else-if="row.min_weekly_hours != null">
            至少 {{ row.min_weekly_hours }} 节
          </span>
          <span v-else style="color: #909399">不限</span>
        </template>
      </el-table-column>
      <el-table-column prop="homeroom_class_name" label="班主任" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button size="small" @click="showDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑教师' : '添加教师'" width="500px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="出差分组">
          <el-select v-model="form.travel_group" clearable placeholder="请选择">
            <el-option
              v-for="g in travelGroups"
              :key="g.id"
              :label="g.name"
              :value="g.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="校本课程分组">
          <el-select
            v-model="form.combined_class_group"
            clearable
            placeholder="留空自动分配"
            :disabled="form.exclude_from_combined"
          >
            <el-option
              v-for="g in combinedGroups"
              :key="g.id"
              :label="g.name"
              :value="g.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="不参与校本课程">
          <el-switch v-model="form.exclude_from_combined" />
          <span style="color: #909399; font-size: 12px; margin-left: 10px">
            勾选后该教师不会被分配到校本课程
          </span>
        </el-form-item>
        <el-form-item label="周课时范围">
          <div style="display: flex; align-items: center; gap: 10px;">
            <el-input-number
              v-model="form.min_weekly_hours"
              :min="1"
              :max="30"
              placeholder="不限"
              controls-position="right"
              style="width: 130px"
            />
            <span>~</span>
            <el-input-number
              v-model="form.max_weekly_hours"
              :min="1"
              :max="30"
              placeholder="不限"
              controls-position="right"
              style="width: 130px"
            />
            <span style="color: #909399; font-size: 13px;">节</span>
          </div>
          <div style="color: #909399; font-size: 12px; margin-top: 5px">
            留空表示不限制；可只设上限或下限，也可同时设置
          </div>
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
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTeachers, createTeacher, updateTeacher, deleteTeacher } from '../api/teachers'
import api from '../api'

const teachers = ref([])
const travelGroups = ref([])
const combinedGroups = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({
  name: '',
  travel_group: null,
  combined_class_group: null,
  exclude_from_combined: false,
  min_weekly_hours: null,
  max_weekly_hours: null
})

// 当勾选"不参与校本课程"时，清空分组选择
watch(() => form.value.exclude_from_combined, (val) => {
  if (val) {
    form.value.combined_class_group = null
  }
})

const loadData = async () => {
  teachers.value = await getTeachers()
  travelGroups.value = await api.get('/travel-groups/')
  combinedGroups.value = await api.get('/combined-class-groups/')
}

const showDialog = (row = null) => {
  if (row) {
    editingId.value = row.id
    form.value = {
      name: row.name,
      travel_group: row.travel_group,
      combined_class_group: row.combined_class_group,
      exclude_from_combined: row.exclude_from_combined || false,
      min_weekly_hours: row.min_weekly_hours,
      max_weekly_hours: row.max_weekly_hours
    }
  } else {
    editingId.value = null
    form.value = {
      name: '',
      travel_group: null,
      combined_class_group: null,
      exclude_from_combined: false,
      min_weekly_hours: null,
      max_weekly_hours: null
    }
  }
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    if (editingId.value) {
      await updateTeacher(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createTeacher(form.value)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm('确定删除该教师?', '提示', { type: 'warning' })
  try {
    await deleteTeacher(row.id)
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
