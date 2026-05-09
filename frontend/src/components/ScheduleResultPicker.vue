<template>
  <div class="result-picker" :class="{ inline }">
    <template v-if="!inline">
      <div class="picker-summary">
        <div class="picker-summary__info">
          <template v-if="currentResult">
            <div class="picker-summary__title-row">
              <el-icon v-if="currentResult.is_favorite" class="star-icon active"><StarFilled /></el-icon>
              <span class="summary-name">{{ getScheduleResultDisplayName(currentResult) }}</span>
              <el-tag
                :type="getScheduleResultStatusType(currentResult.solve_status)"
                size="small"
              >
                {{ getScheduleResultStatusText(currentResult.solve_status) }}
              </el-tag>
              <el-tag v-if="currentResult.is_active" type="success" size="small" effect="dark">
                使用中
              </el-tag>
            </div>
            <div class="picker-summary__meta">
              <span class="summary-time">{{ currentResult.created_at }}</span>
            </div>
          </template>
          <span v-else class="summary-empty">未选择排课结果</span>
        </div>

        <el-button type="primary" plain @click="openDrawer">
          <el-icon><Menu /></el-icon>
          <span>切换 / 管理</span>
        </el-button>
      </div>

      <el-drawer
        v-model="drawerOpen"
        title="排课结果管理"
        direction="rtl"
        :size="isMobile ? '100%' : '860px'"
        :destroy-on-close="false"
      >
        <ResultTable
          ref="tableRef"
          :selected-id="modelValue"
          :show-activate-action="showActivateAction"
          @select-row="onRowSelectAndClose"
          @activated="onActivated"
          @changed="onTableChanged"
        />
      </el-drawer>
    </template>

    <ResultTable
      v-else
      ref="tableRef"
      :selected-id="modelValue"
      :show-activate-action="showActivateAction"
      @select-row="onRowSelect"
      @activated="onActivated"
      @changed="onTableChanged"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Menu, StarFilled } from '@element-plus/icons-vue'
import { useResponsive } from '../composables/useResponsive'
import {
  getScheduleResultDisplayName,
  getScheduleResultStatusText,
  getScheduleResultStatusType
} from '../utils/scheduleResults'
import ResultTable from './ScheduleResultTable.vue'

const props = defineProps({
  modelValue: { type: [Number, String], default: null },
  currentResult: { type: Object, default: null },
  inline: { type: Boolean, default: false },
  showActivateAction: { type: Boolean, default: true }
})

const emit = defineEmits(['update:modelValue', 'refresh'])

const drawerOpen = ref(false)
const tableRef = ref(null)
const { isMobile } = useResponsive()

const openDrawer = () => {
  drawerOpen.value = true
  tableRef.value?.refresh()
}

const onRowSelect = (row) => {
  emit('update:modelValue', row.id)
}

const onRowSelectAndClose = (row) => {
  emit('update:modelValue', row.id)
  drawerOpen.value = false
}

const onActivated = (row) => {
  emit('update:modelValue', row.id)
  emit('refresh')
}

const onTableChanged = (payload = {}) => {
  const deleted = payload.deletedIds || []
  if (deleted.includes(props.modelValue)) {
    emit('update:modelValue', null)
  }
  emit('refresh')
}

defineExpose({
  refresh: () => tableRef.value?.refresh()
})
</script>

<style scoped>
.picker-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.picker-summary__info {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.picker-summary__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.picker-summary__meta {
  color: #909399;
  font-size: 13px;
}

.summary-name {
  font-weight: 600;
  color: #303133;
}

.summary-time {
  color: #909399;
  font-size: 13px;
}

.summary-empty {
  color: #909399;
}

.star-icon {
  color: #f0a020;
}

.result-picker.inline {
  width: 100%;
}

@media (max-width: 768px) {
  .picker-summary {
    align-items: stretch;
  }
}
</style>
