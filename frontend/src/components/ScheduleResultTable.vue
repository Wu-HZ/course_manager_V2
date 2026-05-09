<template>
  <div class="result-table">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="search"
          placeholder="按名称搜索"
          clearable
          size="small"
          class="toolbar-control toolbar-control--search"
          @input="onFilterChange"
        />
        <el-select
          v-model="statusFilter"
          placeholder="所有状态"
          clearable
          size="small"
          class="toolbar-control toolbar-control--status"
          @change="onFilterChange"
        >
          <el-option
            v-for="opt in STATUS_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-switch
          v-model="favoriteOnly"
          active-text="只看收藏"
          @change="onFilterChange"
        />
      </div>

      <div class="toolbar-right">
        <el-button
          size="small"
          :disabled="!selectedRows.length"
          :loading="actionLoading"
          @click="onBulkFavorite(true)"
        >
          <el-icon><StarFilled /></el-icon>
          批量收藏
        </el-button>
        <el-button
          size="small"
          :disabled="!selectedRows.length"
          :loading="actionLoading"
          @click="onBulkFavorite(false)"
        >
          <el-icon><Star /></el-icon>
          取消收藏
        </el-button>
        <el-button
          size="small"
          type="danger"
          plain
          :disabled="!selectedRows.length"
          :loading="actionLoading"
          @click="onBulkDelete"
        >
          <el-icon><Delete /></el-icon>
          批量删除 ({{ selectedRows.length }})
        </el-button>
      </div>
    </div>

    <div v-if="isMobile" class="mobile-result-list" v-loading="loading">
      <el-empty v-if="!items.length && !loading" description="暂无排课结果" />

      <template v-else>
        <el-card
          v-for="row in items"
          :key="row.id"
          class="mobile-result-card"
          shadow="hover"
          :class="{ 'mobile-result-card--selected': row.id === selectedId }"
        >
          <div class="mobile-result-card__top">
            <el-checkbox
              :model-value="isSelected(row.id)"
              @change="checked => onCardSelectionChange(row, checked)"
              @click.stop
            />
            <el-button
              link
              class="star-btn"
              :class="{ active: row.is_favorite }"
              @click.stop="onToggleFavorite(row)"
            >
              <el-icon><StarFilled v-if="row.is_favorite" /><Star v-else /></el-icon>
            </el-button>
          </div>

          <button type="button" class="mobile-result-card__summary" @click="emit('select-row', row)">
            <div class="mobile-result-card__name">
              {{ getScheduleResultDisplayName(row) }}
            </div>
            <div class="mobile-result-card__meta">
              <el-tag
                :type="getScheduleResultStatusType(row.solve_status)"
                size="small"
              >
                {{ getScheduleResultStatusText(row.solve_status) }}
              </el-tag>
              <el-tag v-if="row.is_active" type="success" size="small" effect="dark">使用中</el-tag>
            </div>
            <div class="mobile-meta-list">
              <div class="mobile-meta-list__item">
                <span class="mobile-meta-list__label">创建时间</span>
                <span class="mobile-meta-list__value">{{ row.created_at }}</span>
              </div>
              <div class="mobile-meta-list__item">
                <span class="mobile-meta-list__label">条目数</span>
                <span class="mobile-meta-list__value">{{ row.entry_count }}</span>
              </div>
            </div>
          </button>

          <div class="mobile-result-card__actions">
            <el-button
              v-if="showActivateAction && !row.is_active && canActivate(row)"
              size="small"
              :loading="actionLoading"
              @click.stop="onActivate(row)"
            >
              激活
            </el-button>
            <el-button
              size="small"
              :loading="actionLoading"
              @click.stop="onRename(row)"
            >
              改名
            </el-button>
            <el-button
              size="small"
              type="danger"
              plain
              :loading="actionLoading"
              @click.stop="onDeleteRow(row)"
            >
              删除
            </el-button>
          </div>
        </el-card>
      </template>
    </div>

    <div v-else class="responsive-table-wrapper">
      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="items"
        stripe
        border
        highlight-current-row
        :row-class-name="rowClassName"
        @selection-change="onSelectionChange"
        @row-click="onRowClick"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column label="★" width="48" align="center">
          <template #default="{ row }">
            <el-button
              link
              class="star-btn"
              :class="{ active: row.is_favorite }"
              @click.stop="onToggleFavorite(row)"
            >
              <el-icon><StarFilled v-if="row.is_favorite" /><Star v-else /></el-icon>
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="名称" min-width="180">
          <template #default="{ row }">
            <span :class="{ 'row-selected-name': row.id === selectedId }">
              {{ getScheduleResultDisplayName(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="getScheduleResultStatusType(row.solve_status)"
              size="small"
            >
              {{ getScheduleResultStatusText(row.solve_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" prop="created_at" width="170" />
        <el-table-column label="条目数" prop="entry_count" width="80" align="center" />
        <el-table-column label="当前" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" type="success" size="small" effect="dark">使用中</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="showActivateAction ? 220 : 160" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="showActivateAction && !row.is_active && canActivate(row)"
              size="small"
              :loading="actionLoading"
              @click.stop="onActivate(row)"
            >
              激活
            </el-button>
            <el-button
              size="small"
              :loading="actionLoading"
              @click.stop="onRename(row)"
            >
              改名
            </el-button>
            <el-button
              size="small"
              type="danger"
              plain
              :loading="actionLoading"
              @click.stop="onDeleteRow(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pagination-bar">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100, 200]"
        :total="total"
        :layout="paginationLayout"
        :pager-count="isMobile ? 5 : 7"
        small
        background
        @size-change="onPageSizeChange"
        @current-change="fetchData"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Star, StarFilled, Delete } from '@element-plus/icons-vue'
import { useResponsive } from '../composables/useResponsive'
import {
  getScheduleResults, updateScheduleResult, deleteScheduleResult,
  bulkDeleteScheduleResults, activateResult, toggleFavoriteScheduleResult
} from '../api/scheduler'
import {
  getScheduleResultDisplayName,
  getScheduleResultStatusText,
  getScheduleResultStatusType
} from '../utils/scheduleResults'

const STATUS_OPTIONS = [
  { value: 'OPTIMAL', label: '最优解' },
  { value: 'FEASIBLE', label: '可行解' },
  { value: 'INFEASIBLE', label: '无可行解' },
  { value: 'MODEL_INVALID', label: '模型无效' },
  { value: 'UNKNOWN', label: '未知' }
]

const props = defineProps({
  selectedId: { type: [Number, String], default: null },
  showActivateAction: { type: Boolean, default: true }
})

const emit = defineEmits(['select-row', 'activated', 'changed'])

const { isMobile } = useResponsive()
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const actionLoading = ref(false)
const search = ref('')
const favoriteOnly = ref(false)
const statusFilter = ref('')
const selectedRows = ref([])
const tableRef = ref(null)

let searchDebounce = null

const paginationLayout = computed(() => (
  isMobile.value
    ? 'prev, pager, next'
    : 'total, sizes, prev, pager, next, jumper'
))

const isDialogCancelled = (error) => (
  error === 'cancel' || error === 'close' ||
  error?.action === 'cancel' || error?.action === 'close'
)

const buildParams = () => {
  const params = { page: page.value, page_size: pageSize.value }
  if (favoriteOnly.value) params.is_favorite = true
  if (statusFilter.value) params.solve_status = statusFilter.value
  if (search.value.trim()) params.search = search.value.trim()
  return params
}

const clearSelection = async () => {
  selectedRows.value = []
  await nextTick()
  tableRef.value?.clearSelection?.()
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getScheduleResults(buildParams())
    items.value = res.results || []
    total.value = res.count || 0
    await clearSelection()
  } catch {
    ElMessage.error('加载排课结果失败')
  } finally {
    loading.value = false
  }
}

const onFilterChange = () => {
  clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    page.value = 1
    fetchData()
  }, 250)
}

const onPageSizeChange = () => {
  page.value = 1
  fetchData()
}

const canActivate = (row) => (
  row.solve_status === 'OPTIMAL' || row.solve_status === 'FEASIBLE'
)

const rowClassName = ({ row }) => (
  row.id === props.selectedId ? 'current-selected-row' : ''
)

const onSelectionChange = (rows) => {
  selectedRows.value = rows
}

const isSelected = (rowId) => selectedRows.value.some(row => row.id === rowId)

const onCardSelectionChange = (row, checked) => {
  if (checked) {
    if (!isSelected(row.id)) {
      selectedRows.value = [...selectedRows.value, row]
    }
    return
  }
  selectedRows.value = selectedRows.value.filter(item => item.id !== row.id)
}

const onRowClick = (row, column) => {
  if (column?.type === 'selection') return
  if (column?.label === '操作' || column?.label === '★') return
  emit('select-row', row)
}

const onToggleFavorite = async (row) => {
  actionLoading.value = true
  try {
    await toggleFavoriteScheduleResult(row.id, !row.is_favorite)
    await fetchData()
    emit('changed')
  } catch {
    ElMessage.error('收藏状态更新失败')
  } finally {
    actionLoading.value = false
  }
}

const onRename = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt(
      '输入新的课表名称，留空将恢复默认名称。',
      '重命名课表',
      {
        confirmButtonText: '保存',
        cancelButtonText: '取消',
        inputValue: row.name || '',
        inputPlaceholder: '例如：三月试排 V2'
      }
    )
    actionLoading.value = true
    await updateScheduleResult(row.id, { name: value.trim() })
    ElMessage.success(value.trim() ? '课表名称已更新' : '已恢复默认课表名称')
    await fetchData()
    emit('changed')
  } catch (e) {
    if (isDialogCancelled(e)) return
    ElMessage.error('重命名失败')
  } finally {
    actionLoading.value = false
  }
}

const onDeleteRow = async (row) => {
  const name = getScheduleResultDisplayName(row)
  try {
    await ElMessageBox.confirm(
      `确定删除“${name}”吗？删除后该次排课结果及课表条目都会一起移除。`,
      '删除课表',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    actionLoading.value = true
    await deleteScheduleResult(row.id)
    ElMessage.success(`已删除 ${name}`)
    await fetchData()
    emit('changed', { deletedIds: [row.id] })
  } catch (e) {
    if (isDialogCancelled(e)) return
    ElMessage.error('删除失败')
  } finally {
    actionLoading.value = false
  }
}

const onBulkDelete = async () => {
  if (!selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedRows.value.length} 条排课结果吗？此操作不可撤销。`,
      '批量删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    actionLoading.value = true
    const ids = selectedRows.value.map(r => r.id)
    const res = await bulkDeleteScheduleResults(ids)
    ElMessage.success(`已删除 ${res.deleted ?? ids.length} 条`)
    await fetchData()
    emit('changed', { deletedIds: ids })
  } catch (e) {
    if (isDialogCancelled(e)) return
    ElMessage.error('批量删除失败')
  } finally {
    actionLoading.value = false
  }
}

const onBulkFavorite = async (isFavorite) => {
  if (!selectedRows.value.length) return
  actionLoading.value = true
  try {
    await Promise.all(
      selectedRows.value
        .filter(r => r.is_favorite !== isFavorite)
        .map(r => updateScheduleResult(r.id, { is_favorite: isFavorite }))
    )
    ElMessage.success(isFavorite ? '已标记为收藏' : '已取消收藏')
    await fetchData()
    emit('changed')
  } catch {
    ElMessage.error('批量操作失败')
  } finally {
    actionLoading.value = false
  }
}

const onActivate = async (row) => {
  actionLoading.value = true
  try {
    await activateResult(row.id)
    ElMessage.success(`已激活 ${getScheduleResultDisplayName(row)}`)
    await fetchData()
    emit('activated', row)
    emit('changed')
  } catch {
    ElMessage.error('激活失败')
  } finally {
    actionLoading.value = false
  }
}

defineExpose({ refresh: fetchData })

onMounted(fetchData)
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar-control--search {
  width: 180px;
}

.toolbar-control--status {
  width: 140px;
}

.mobile-result-list {
  display: grid;
  gap: 12px;
}

.mobile-result-card {
  border-radius: 14px;
}

.mobile-result-card--selected {
  border-color: #409eff;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.24);
}

.mobile-result-card__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mobile-result-card__summary {
  width: 100%;
  display: grid;
  gap: 12px;
  margin-top: 12px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.mobile-result-card__name {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
  color: #303133;
}

.mobile-result-card__meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.mobile-result-card__actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.mobile-result-card__actions :deep(.el-button) {
  margin-left: 0;
}

.star-btn {
  color: #c0c4cc;
  font-size: 18px;
  padding: 4px;
}

.star-btn.active {
  color: #f0a020;
}

.row-selected-name {
  font-weight: 600;
  color: #409eff;
}

:deep(.current-selected-row) {
  background-color: #ecf5ff !important;
}

.pagination-bar {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .toolbar-left,
  .toolbar-right,
  .pagination-bar {
    width: 100%;
  }

  .toolbar-control--search,
  .toolbar-control--status {
    width: 100%;
  }

  .pagination-bar {
    justify-content: center;
  }
}
</style>
