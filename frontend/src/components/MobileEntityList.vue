<template>
  <div class="mobile-entity-list">
    <el-empty
      v-if="!items.length"
      :description="emptyDescription"
      class="mobile-entity-list__empty"
    />

    <template v-else>
      <el-card
        v-for="item in items"
        :key="itemKey(item)"
        class="mobile-entity-list__card"
        shadow="hover"
      >
        <div class="mobile-entity-list__header">
          <div class="mobile-entity-list__heading">
            <div class="mobile-entity-list__title">
              <slot name="title" :item="item" />
            </div>
            <div v-if="$slots.subtitle" class="mobile-entity-list__subtitle">
              <slot name="subtitle" :item="item" />
            </div>
          </div>
          <div v-if="$slots.headerExtra" class="mobile-entity-list__header-extra">
            <slot name="headerExtra" :item="item" />
          </div>
        </div>

        <div v-if="$slots.meta" class="mobile-entity-list__meta">
          <slot name="meta" :item="item" />
        </div>

        <div v-if="$slots.actions" class="mobile-entity-list__actions">
          <slot name="actions" :item="item" />
        </div>
      </el-card>
    </template>
  </div>
</template>

<script setup>
const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  itemKeyField: {
    type: String,
    default: 'id',
  },
  emptyDescription: {
    type: String,
    default: '暂无数据',
  },
})

const itemKey = (item) => item?.[props.itemKeyField] ?? JSON.stringify(item)
</script>

<style scoped>
.mobile-entity-list {
  display: grid;
  gap: 12px;
}

.mobile-entity-list__card {
  border-radius: 14px;
}

.mobile-entity-list__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.mobile-entity-list__heading {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.mobile-entity-list__title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  word-break: break-word;
}

.mobile-entity-list__subtitle {
  font-size: 12px;
  line-height: 1.5;
  color: #909399;
}

.mobile-entity-list__header-extra {
  flex-shrink: 0;
}

.mobile-entity-list__meta {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.mobile-entity-list__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.mobile-entity-list__actions :deep(.el-button) {
  margin-left: 0;
}

.mobile-entity-list__empty {
  padding: 28px 0;
  background: #fff;
  border-radius: 14px;
}
</style>
