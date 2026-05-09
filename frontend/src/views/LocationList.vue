<template>
  <div class="page-container">
    <div class="page-header">
      <h2>场地管理</h2>
      <el-button type="primary" @click="showDialog()">
        <el-icon><Plus /></el-icon> 添加场地
      </el-button>
    </div>

    <MobileEntityList v-if="isMobile" :items="locations" empty-description="暂无场地数据">
      <template #title="{ item }">
        {{ item.name }}
      </template>
      <template #subtitle="{ item }">
        {{ item.location_type_display }}
      </template>
      <template #meta="{ item }">
        <div class="mobile-meta-list">
          <div class="mobile-meta-list__item">
            <span class="mobile-meta-list__label">同时容纳班数</span>
            <span class="mobile-meta-list__value">{{ item.capacity }}</span>
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
      <el-table :data="locations" stripe border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="场地名称" min-width="180" />
        <el-table-column prop="location_type_display" label="场地类型" min-width="160" />
        <el-table-column prop="capacity" label="同时容纳班数" width="140" />
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
      :title="editingId ? '编辑场地' : '添加场地'"
      :fullscreen="isMobile"
      :width="isMobile ? undefined : '500px'"
      class="responsive-dialog"
    >
      <el-form
        :model="form"
        :label-position="isMobile ? 'top' : 'right'"
        label-width="120px"
        class="responsive-form"
      >
        <el-form-item label="场地名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="场地类型" required>
          <el-select v-model="form.location_type">
            <el-option label="普通教室" value="NORMAL" />
            <el-option label="操场" value="PLAYGROUND" />
            <el-option label="实验室" value="LAB" />
            <el-option label="家政室" value="HOME_EC" />
          </el-select>
        </el-form-item>
        <el-form-item label="同时容纳班数" required>
          <el-input-number v-model="form.capacity" :min="1" :max="10" />
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
import { getLocations, createLocation, updateLocation, deleteLocation } from '../api/resources'

const locations = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({ name: '', location_type: 'NORMAL', capacity: 1 })

const { isMobile } = useResponsive()

const loadData = async () => {
  locations.value = await getLocations()
}

const showDialog = (row = null) => {
  if (row) {
    editingId.value = row.id
    form.value = {
      name: row.name,
      location_type: row.location_type,
      capacity: row.capacity
    }
  } else {
    editingId.value = null
    form.value = { name: '', location_type: 'NORMAL', capacity: 1 }
  }
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    if (editingId.value) {
      await updateLocation(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createLocation(form.value)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm('确定删除该场地?', '提示', { type: 'warning' })
  try {
    await deleteLocation(row.id)
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
