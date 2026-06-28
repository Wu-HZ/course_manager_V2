<template>
  <div class="page-container">
    <div class="page-header">
      <h2>课程管理</h2>
      <el-button type="primary" @click="showDialog()">
        <el-icon><Plus /></el-icon> 添加课程
      </el-button>
    </div>

    <MobileEntityList v-if="isMobile" :items="subjects" empty-description="暂无课程数据">
      <template #title="{ item }">
        {{ item.name }}
      </template>
      <template #subtitle="{ item }">
        周课时 {{ item.weekly_hours }} 节
      </template>
      <template #headerExtra="{ item }">
        <div class="subject-tags">
          <el-tag v-if="item.is_main_subject" type="danger" size="small">主课</el-tag>
          <el-tag v-if="item.is_combined_class" type="warning" size="small">合班课</el-tag>
        </div>
      </template>
      <template #meta="{ item }">
        <div class="mobile-meta-list">
          <div class="mobile-meta-list__item">
            <span class="mobile-meta-list__label">场地类型</span>
            <span class="mobile-meta-list__value">{{ item.location_type_display }}</span>
          </div>
          <div class="mobile-meta-list__item">
            <span class="mobile-meta-list__label">适用年级</span>
            <span class="mobile-meta-list__value">{{ item.applicable_grades || '全部' }}</span>
          </div>
          <div class="mobile-meta-list__item">
            <span class="mobile-meta-list__label">排课规则</span>
            <div class="mobile-meta-list__value subject-tags">
              <el-tag :type="item.is_am_preferred ? 'success' : 'info'" size="small">
                {{ item.is_am_preferred ? '上午优先' : '不限制上午' }}
              </el-tag>
              <el-tag :type="item.allow_consecutive ? 'success' : 'info'" size="small">
                {{ item.allow_consecutive ? '允许连堂' : '不连堂' }}
              </el-tag>
              <el-tag :type="item.avoid_first_period ? 'warning' : 'info'" size="small">
                {{ item.avoid_first_period ? '避开第一节' : '首节可排' }}
              </el-tag>
            </div>
          </div>
          <div class="mobile-meta-list__item">
            <span class="mobile-meta-list__label">限制参数</span>
            <span class="mobile-meta-list__value">
              单日上限 {{ item.max_daily_limit }} 节 · 单师班数 {{ item.max_teacher_classes }}
            </span>
          </div>
        </div>
      </template>
      <template #actions="{ item }">
        <el-button @click="showDialog(item)">编辑</el-button>
        <el-button type="danger" plain @click="handleDelete(item)">删除</el-button>
      </template>
    </MobileEntityList>

    <div v-else class="responsive-table-wrapper">
      <el-table :data="subjects" stripe border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="课程名称" min-width="160" />
        <el-table-column prop="weekly_hours" label="周课时" width="90" />
        <el-table-column label="上午优先" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_am_preferred" type="success" size="small">是</el-tag>
            <el-tag v-else type="info" size="small">否</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="主课" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_main_subject" type="danger" size="small">是</el-tag>
            <el-tag v-else type="info" size="small">否</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="允许连堂" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.allow_consecutive" type="success" size="small">是</el-tag>
            <el-tag v-else type="info" size="small">否</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="max_daily_limit" label="单日上限" width="100" />
        <el-table-column prop="max_teacher_classes" label="单师班数" width="100" />
        <el-table-column prop="location_type_display" label="场地类型" min-width="140" />
        <el-table-column label="合班课" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_combined_class" type="warning" size="small">是</el-tag>
            <el-tag v-else type="info" size="small">否</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="适用年级" width="120">
          <template #default="{ row }">
            <span>{{ row.applicable_grades || '全部' }}</span>
          </template>
        </el-table-column>
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
      :title="editingId ? '编辑课程' : '添加课程'"
      :fullscreen="isMobile"
      :width="isMobile ? undefined : '600px'"
      class="responsive-dialog"
    >
      <el-form
        :model="form"
        :label-position="isMobile ? 'top' : 'right'"
        label-width="100px"
        class="responsive-form"
      >
        <el-form-item label="课程名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="周课时" required>
          <el-input-number v-model="form.weekly_hours" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="单日上限">
          <el-input-number v-model="form.max_daily_limit" :min="1" :max="4" />
        </el-form-item>
        <el-form-item label="单师最多班数">
          <el-input-number v-model="form.max_teacher_classes" :min="1" :max="5" />
          <div class="form-note">
            同一教师最多教几个班的该课程，1 表示只教 1 个班
          </div>
        </el-form-item>
        <el-form-item label="场地类型">
          <el-select v-model="form.location_type">
            <el-option label="普通教室" value="NORMAL" />
            <el-option label="操场" value="PLAYGROUND" />
            <el-option label="实验室" value="LAB" />
            <el-option label="家政室" value="HOME_EC" />
          </el-select>
        </el-form-item>
        <el-form-item label="排课选项">
          <div class="subject-options">
            <el-checkbox v-model="form.is_main_subject">主课</el-checkbox>
            <el-checkbox v-model="form.is_am_preferred">上午优先</el-checkbox>
            <el-checkbox v-model="form.allow_consecutive">允许连堂</el-checkbox>
            <el-checkbox v-model="form.is_combined_class">合班课</el-checkbox>
            <el-checkbox v-model="form.avoid_first_period">避开第一节</el-checkbox>
          </div>
        </el-form-item>
        <el-form-item label="适用年级">
          <el-input v-model="form.applicable_grades" placeholder="如 1,2,3；留空表示所有年级" />
          <div class="form-note">
            使用逗号分隔年级编号；留空表示所有年级都开设此课程
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
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MobileEntityList from '../components/MobileEntityList.vue'
import { useResponsive } from '../composables/useResponsive'
import { getSubjects, createSubject, updateSubject, deleteSubject } from '../api/subjects'
import api from '../api'

const subjects = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const classMeetingName = ref('班会')
const form = ref({
  name: '',
  weekly_hours: 1,
  is_main_subject: false,
  is_am_preferred: false,
  allow_consecutive: false,
  max_daily_limit: 1,
  max_teacher_classes: 1,
  location_type: 'NORMAL',
  is_combined_class: false,
  applicable_grades: '',
  avoid_first_period: false
})

const { isMobile } = useResponsive()

/** 班会或校本课程：系统通过名称匹配/合班课标志来预锁定，不应随意修改或删除 */
const isSpecialSubject = (row) => {
  if (!row) return false
  return row.is_combined_class || row.name === classMeetingName.value
}

const getSpecialTypeLabel = (row) => {
  if (!row) return ''
  if (row.is_combined_class) return '校本课程（合班课）'
  if (row.name === classMeetingName.value) return '班会课'
  return ''
}

const confirmSpecialAction = async (action, row) => {
  const typeLabel = getSpecialTypeLabel(row)
  const message = `「${row.name}」是${typeLabel}，属于系统预锁定的固定课程。

⚠️ ${action === 'edit' ? '修改其字段（名称除外）对排课行为没有实际影响；若修改名称，则需同步更新「排课设置」中的对应设置项。' : '删除后将导致排课结果中所有该课程的条目被级联删除，课表中将不再出现该课程。'}

确定要继续${action === 'edit' ? '修改' : '删除'}吗？`
  await ElMessageBox.confirm(message, `确认${action === 'edit' ? '修改' : '删除'}特殊课程`, {
    confirmButtonText: `确认${action === 'edit' ? '修改' : '删除'}`,
    cancelButtonText: '取消',
    type: 'warning',
    dangerouslyUseHTMLString: false
  })
}

const loadData = async () => {
  subjects.value = await getSubjects()
}

const showDialog = async (row = null) => {
  if (row) {
    editingId.value = row.id
    form.value = { ...row }
    if (isSpecialSubject(row)) {
      try {
        await confirmSpecialAction('edit', row)
      } catch {
        return
      }
    }
  } else {
    editingId.value = null
    form.value = {
      name: '',
      weekly_hours: 1,
      is_main_subject: false,
      is_am_preferred: false,
      allow_consecutive: false,
      max_daily_limit: 1,
      max_teacher_classes: 1,
      location_type: 'NORMAL',
      is_combined_class: false,
      applicable_grades: '',
      avoid_first_period: false
    }
  }
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    if (editingId.value) {
      await updateSubject(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createSubject(form.value)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleDelete = async (row) => {
  try {
    if (isSpecialSubject(row)) {
      await confirmSpecialAction('delete', row)
    } else {
      await ElMessageBox.confirm('确定删除该课程?', '提示', { type: 'warning' })
    }
  } catch {
    return
  }
  try {
    await deleteSubject(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const loadSettings = async () => {
  try {
    const settings = await api.get('/scheduler-settings/')
    classMeetingName.value = settings.class_meeting_name || '班会'
  } catch {
    // 设置加载失败则使用默认值
  }
}

onMounted(async () => {
  await loadSettings()
  loadData()
})
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

.subject-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.subject-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 12px;
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

  .subject-options {
    grid-template-columns: 1fr;
  }
}
</style>
