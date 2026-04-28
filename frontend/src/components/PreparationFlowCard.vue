<template>
  <el-card class="flow-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">本学期排课准备</div>
          <div class="card-subtitle">
            下面每一步都对应一个独立入口或独立动作，不再把多个设置项合并到同一个步骤里。
          </div>
        </div>
        <div class="header-tags">
          <el-tag :type="precheck.summary.can_run ? 'success' : 'warning'" effect="light">
            {{ precheck.summary.can_run ? '可以排课' : '暂不可排课' }}
          </el-tag>
          <el-tag type="info" effect="light">
            已完成 {{ precheck.summary.completed_steps }}/{{ precheck.summary.total_steps }}
          </el-tag>
        </div>
      </div>
    </template>

    <div class="step-list">
      <div
        v-for="(step, index) in precheck.steps"
        :key="step.key"
        class="step-item"
        :class="`status-${step.status}`"
      >
        <div class="step-index">{{ index + 1 }}</div>
        <div class="step-content">
          <div class="step-top">
            <div>
              <div class="step-title">{{ step.title }}</div>
              <div class="step-description">{{ step.description }}</div>
            </div>
            <el-tag :type="getPrecheckStatusType(step.status)" effect="light">
              {{ getPrecheckStatusLabel(step.status) }}
            </el-tag>
          </div>
          <div class="step-detail">{{ step.detail }}</div>
          <div v-if="step.actions?.length" class="step-actions">
            <el-button
              v-for="action in step.actions"
              :key="`${step.key}-${action.route}`"
              size="small"
              plain
              @click="router.push(action.route)"
            >
              {{ action.label }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { getPrecheckStatusLabel, getPrecheckStatusType } from '../utils/precheck'

defineProps({
  precheck: {
    type: Object,
    required: true,
  },
})

const router = useRouter()
</script>

<style scoped>
.flow-card {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.card-subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.header-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.step-list {
  display: grid;
  gap: 14px;
}

.step-item {
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 14px;
  align-items: flex-start;
}

.step-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #f5f7fa;
  color: #606266;
  font-weight: 700;
}

.step-item.status-completed .step-index {
  background: #f0f9eb;
  color: #67c23a;
}

.step-item.status-ready .step-index {
  background: #ecf5ff;
  color: #409eff;
}

.step-item.status-warning .step-index {
  background: #fdf6ec;
  color: #e6a23c;
}

.step-item.status-blocked .step-index {
  background: #fef0f0;
  color: #f56c6c;
}

.step-content {
  padding: 14px 16px;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  background: #fff;
}

.step-item.status-blocked .step-content {
  border-color: #f8d7da;
  background: #fffafa;
}

.step-item.status-warning .step-content {
  border-color: #f5dab1;
  background: #fffdf7;
}

.step-item.status-ready .step-content {
  border-color: #c6e2ff;
  background: #f7fbff;
}

.step-top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.step-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.step-description {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.step-detail {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.7;
  color: #606266;
}

.step-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

@media (max-width: 768px) {
  .card-header,
  .step-top {
    flex-direction: column;
  }

  .header-tags {
    justify-content: flex-start;
  }

  .step-item {
    grid-template-columns: 1fr;
  }
}
</style>
