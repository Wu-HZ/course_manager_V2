<template>
  <div class="page-container">
    <div class="page-header">
      <h2>班级管理</h2>
      <el-button type="primary" @click="showDialog()">
        <el-icon><Plus /></el-icon> 添加班级
      </el-button>
    </div>

    <MobileEntityList v-if="isMobile" :items="classes" empty-description="暂无班级数据">
      <template #title="{ item }">
        {{ item.name }}
      </template>
      <template #subtitle="{ item }">
        年级 {{ item.grade }}
      </template>
      <template #meta="{ item }">
        <div class="mobile-meta-list">
          <div class="mobile-meta-list__item">
            <span class="mobile-meta-list__label">班主任</span>
            <span class="mobile-meta-list__value">{{ item.homeroom_teacher_name || '未设置' }}</span>
          </div>
          <div class="mobile-meta-list__item">
            <span class="mobile-meta-list__label">记录编号</span>
            <span class="mobile-meta-list__value">ID {{ item.id }}</span>
          </div>
        </div>
      </template>
      <template #actions="{ item }">
        <el-button @click="showDialog(item)">编辑</el-button>
        <el-button type="danger" plain @click="handleDelete(item)">删除</el-button>
      </template>
    </MobileEntityList>

    <div v-else class="responsive-table-wrapper">
      <el-table :data="classes" stripe border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="班级名称" min-width="150" />
        <el-table-column prop="grade" label="年级" width="90" />
        <el-table-column prop="homeroom_teacher_name" label="班主任" min-width="120" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑班级' : '添加班级'"
      :fullscreen="isMobile"
      :width="isMobile ? undefined : '500px'"
      class="responsive-dialog"
    >
      <el-form
        :model="form"
        :label-position="isMobile ? 'top' : 'right'"
        label-width="100px"
        class="responsive-form"
      >
        <el-form-item label="班级名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="年级" required>
          <el-input-number v-model="form.grade" :min="1" :max="9" />
        </el-form-item>
        <el-form-item label="班主任">
          <el-select v-model="form.homeroom_teacher" clearable placeholder="请选择">
            <el-option
              v-for="t in teachers"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSave">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MobileEntityList from '../components/MobileEntityList.vue'
import { useResponsive } from '../composables/useResponsive'
import { getClasses, createClass, updateClass, deleteClass } from '../api/classes'
import { getTeachers } from '../api/teachers'

const classes = ref([])
const teachers = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({ name: '', grade: 1, homeroom_teacher: null })

const { isMobile } = useResponsive()

const loadData = async () => {
  classes.value = await getClasses()
  teachers.value = await getTeachers()
}

const showDialog = (row = null) => {
  if (row) {
    editingId.value = row.id
    form.value = {
      name: row.name,
      grade: row.grade,
      homeroom_teacher: row.homeroom_teacher
    }
  } else {
    editingId.value = null
    form.value = { name: '', grade: 1, homeroom_teacher: null }
  }
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    if (editingId.value) {
      await updateClass(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createClass(form.value)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm('确定删除该班级?', '提示', { type: 'warning' })
  try {
    await deleteClass(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.page-container {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
}

@media (max-width: 768px) {
  .page-container {
    padding: 16px;
  }
}
</style>
