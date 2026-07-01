<template>
  <div class="page-container">
    <div class="page-header">
      <h2>教师管理</h2>
      <el-button type="primary" @click="showDialog()">
        <el-icon><Plus /></el-icon> 添加教师
      </el-button>
    </div>

    <MobileEntityList v-if="isMobile" :items="teachers" empty-description="暂无教师数据">
      <template #title="{ item }">
        {{ item.name }}
      </template>
      <template #subtitle="{ item }">
        ID {{ item.id }}
      </template>
      <template #headerExtra="{ item }">
        <el-tag v-if="item.homeroom_class_name" type="success" effect="plain">
          {{ item.homeroom_class_name }}
        </el-tag>
      </template>
      <template #meta="{ item }">
        <div class="mobile-meta-list">
          <div class="mobile-meta-list__item">
            <span class="mobile-meta-list__label">送教分组</span>
            <span class="mobile-meta-list__value">{{ item.travel_group_name || '未分配' }}</span>
          </div>
          <div class="mobile-meta-list__item">
            <span class="mobile-meta-list__label">校本课程</span>
            <span class="mobile-meta-list__value">{{ getCombinedClassLabel(item) }}</span>
          </div>
          <div class="mobile-meta-list__item">
            <span class="mobile-meta-list__label">周课时</span>
            <span class="mobile-meta-list__value">{{ getWeeklyHoursLabel(item) }}</span>
          </div>
          <div class="mobile-meta-list__item">
            <span class="mobile-meta-list__label">班主任</span>
            <span class="mobile-meta-list__value">{{ item.homeroom_class_name || '未设置' }}</span>
          </div>
        </div>
      </template>
      <template #actions="{ item }">
        <el-button @click="showDialog(item)">编辑</el-button>
        <el-button type="danger" plain @click="handleDelete(item)">删除</el-button>
      </template>
    </MobileEntityList>

    <div v-else class="responsive-table-wrapper">
      <el-table :data="teachers" stripe border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="travel_group_name" label="送教分组" min-width="140" />
        <el-table-column label="校本课程" min-width="200">
          <template #default="{ row }">
            {{ getCombinedClassLabel(row) }}
          </template>
        </el-table-column>
        <el-table-column label="周课时" width="150">
          <template #default="{ row }">
            {{ getWeeklyHoursLabel(row) }}
          </template>
        </el-table-column>
        <el-table-column prop="homeroom_class_name" label="班主任" min-width="120" />
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
      :title="editingId ? '编辑教师' : '添加教师'"
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
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="送教分组">
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
        <el-form-item label="校本课程日期">
          <el-select
            v-model="form.combined_class_day"
            clearable
            placeholder="留空自动分配"
            :disabled="form.exclude_from_combined"
          >
            <el-option
              v-for="d in schoolStore.dayOptions"
              :key="d.value"
              :value="d.value"
              :label="d.label"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="不参与校本课程">
          <div class="switch-row">
            <el-switch v-model="form.exclude_from_combined" />
            <span class="form-note">勾选后该教师不会被分配到校本课程</span>
          </div>
        </el-form-item>
        <el-form-item label="周课时范围">
          <div class="hours-range">
            <el-input-number
              v-model="form.min_weekly_hours"
              :min="0"
              :max="30"
              placeholder="最少节数"
              controls-position="right"
              @change="val => form.min_weekly_hours = val === 0 ? null : val"
            />
            <span class="hours-range__separator">~</span>
            <el-input-number
              v-model="form.max_weekly_hours"
              :min="0"
              :max="30"
              placeholder="最多节数"
              controls-position="right"
              @change="val => form.max_weekly_hours = val === 0 ? null : val"
            />
            <span class="hours-range__unit">节</span>
          </div>
          <div class="form-note">
            留空或输入 0 表示不限制；可只设上限或下限，也可同时设置
          </div>
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
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MobileEntityList from '../components/MobileEntityList.vue'
import { useResponsive } from '../composables/useResponsive'
import { getTeachers, createTeacher, updateTeacher, deleteTeacher } from '../api/teachers'
import api from '../api'
import { useSchoolStore } from '../stores/school'

const schoolStore = useSchoolStore()

const teachers = ref([])
const travelGroups = ref([])
const combinedGroups = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({
  name: '',
  travel_group: null,
  combined_class_group: null,
  combined_class_day: null,
  exclude_from_combined: false,
  min_weekly_hours: null,
  max_weekly_hours: null
})

const { isMobile } = useResponsive()

const getCombinedClassLabel = (teacher) => {
  if (teacher.exclude_from_combined) {
    return '不参与'
  }
  if (!teacher.combined_class_group_name) {
    return '自动分组'
  }
  return teacher.combined_class_day_display
    ? `${teacher.combined_class_group_name}（${teacher.combined_class_day_display}）`
    : teacher.combined_class_group_name
}

const getWeeklyHoursLabel = (teacher) => {
  if (teacher.min_weekly_hours != null && teacher.max_weekly_hours != null) {
    return `${teacher.min_weekly_hours}~${teacher.max_weekly_hours} 节`
  }
  if (teacher.max_weekly_hours != null) {
    return `上限 ${teacher.max_weekly_hours} 节`
  }
  if (teacher.min_weekly_hours != null) {
    return `至少 ${teacher.min_weekly_hours} 节`
  }
  return '不限'
}

watch(() => form.value.exclude_from_combined, (val) => {
  if (val) {
    form.value.combined_class_group = null
    form.value.combined_class_day = null
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
      combined_class_day: row.combined_class_day,
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
      combined_class_day: null,
      exclude_from_combined: false,
      min_weekly_hours: null,
      max_weekly_hours: null
    }
  }
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    const data = {
      ...form.value,
      travel_group: form.value.travel_group || null,
      combined_class_group: form.value.combined_class_group || null,
      combined_class_day: form.value.combined_class_day || null,
    }
    if (editingId.value) {
      await updateTeacher(editingId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createTeacher(data)
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

.switch-row {
  display: grid;
  gap: 8px;
}

.hours-range {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.hours-range__separator,
.hours-range__unit {
  color: #909399;
  font-size: 13px;
}

.form-note {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #909399;
}

@media (max-width: 768px) {
  .page-container {
    padding: 16px;
  }

  .hours-range {
    grid-template-columns: 1fr;
  }

  .hours-range__separator,
  .hours-range__unit {
    display: none;
  }
}
</style>
