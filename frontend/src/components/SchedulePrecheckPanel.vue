<template>
  <el-card class="precheck-card" shadow="hover" v-loading="loading">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">排课前检查</div>
          <div class="card-subtitle">
            检查项覆盖排课必需数据，并会校验现有课表锁定是否合法。红色问题会阻止排课，黄色问题仅作提醒。
          </div>
        </div>
        <div class="header-actions">
          <el-tag
            v-if="precheck"
            :type="precheck.summary.can_run ? 'success' : 'danger'"
            effect="dark"
          >
            {{ precheck.summary.can_run ? '必需项已通过' : '存在阻塞项' }}
          </el-tag>
          <el-button
            v-if="precheck"
            text
            @click="detailsCollapsed = !detailsCollapsed"
          >
            {{ detailsCollapsed ? '展开检查详情' : '收起检查详情' }}
          </el-button>
        </div>
      </div>
    </template>

    <template v-if="precheck">
      <div v-if="detailsCollapsed" class="collapsed-summary">
        <div class="collapsed-summary__metrics">
          <div class="metric-item compact">
            <div class="metric-label">校课时量</div>
            <div class="metric-value">{{ precheck.summary.total_school_hours }} 节</div>
            <div class="metric-tip">包含普通课程、校本课程和班会课</div>
          </div>
          <div class="metric-item compact">
            <div class="metric-label">人均课时</div>
            <div class="metric-value">{{ averageTeacherHoursDisplay }} 节/人</div>
            <div class="metric-tip">按全校总课时 ÷ 教师数估算</div>
          </div>
          <div class="metric-item compact">
            <div class="metric-label">建议最少教师数</div>
            <div class="metric-value">{{ estimatedMinTeachersDisplay }} 人</div>
            <div class="metric-tip">按普通课程课时 ÷ 单人最多约 27 节估算</div>
          </div>
        </div>
        <div class="collapsed-summary__footer">
          <div class="footer-summary" :class="{ danger: !precheck.summary.can_run }">
            {{ footerText }}
          </div>
          <el-button size="small" @click="$emit('refresh')">刷新检查结果</el-button>
        </div>
      </div>
      <template v-else>
        <div class="metrics-strip">
          <div class="metric-item">
            <div class="metric-label">校课时量</div>
            <div class="metric-value">{{ precheck.summary.total_school_hours }} 节</div>
            <div class="metric-tip">包含普通课程、校本课程和班会课</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">人均课时</div>
            <div class="metric-value">{{ averageTeacherHoursDisplay }} 节/人</div>
            <div class="metric-tip">按全校总课时 ÷ 教师数估算</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">建议最少教师数</div>
            <div class="metric-value">{{ estimatedMinTeachersDisplay }} 人</div>
            <div class="metric-tip">按普通课程课时 ÷ 单人最多约 27 节估算</div>
          </div>
        </div>

        <div v-if="precheck.blocking_issues.length" class="section">
          <div class="section-title danger">阻塞项</div>
          <div
            v-for="issue in precheck.blocking_issues"
            :key="issue.key"
            class="issue-item issue-danger"
          >
            <div class="issue-title">{{ issue.title }}</div>
            <div class="issue-detail">{{ issue.detail }}</div>
            <div v-if="issue.actions?.length" class="issue-actions">
              <el-button
                v-for="action in issue.actions"
                :key="`${issue.key}-${action.route}`"
                size="small"
                type="danger"
                plain
                @click="router.push(action.route)"
              >
                {{ action.label }}
              </el-button>
            </div>
          </div>
        </div>

        <div v-if="precheck.warning_issues.length" class="section">
          <div class="section-title warning">提醒项</div>
          <div
            v-for="issue in precheck.warning_issues"
            :key="issue.key"
            class="issue-item issue-warning"
          >
            <div class="issue-title">{{ issue.title }}</div>
            <div class="issue-detail">{{ issue.detail }}</div>
            <div v-if="issue.actions?.length" class="issue-actions">
              <el-button
                v-for="action in issue.actions"
                :key="`${issue.key}-${action.route}`"
                size="small"
                plain
                @click="router.push(action.route)"
              >
                {{ action.label }}
              </el-button>
            </div>
          </div>
        </div>

        <div v-if="precheck.passed_checks.length" class="section">
          <div class="section-title success">已通过</div>
          <div class="passed-grid">
            <div
              v-for="item in precheck.passed_checks"
              :key="item.key"
              class="passed-item"
            >
              <div class="passed-title">{{ item.title }}</div>
              <div class="passed-detail">{{ item.detail }}</div>
            </div>
          </div>
        </div>

        <div class="footer-bar">
          <div class="footer-summary" :class="{ danger: !precheck.summary.can_run }">
            {{ footerText }}
          </div>
          <el-button @click="$emit('refresh')">刷新检查结果</el-button>
        </div>
      </template>
    </template>

    <el-empty v-else description="暂无检查结果">
      <el-button @click="$emit('refresh')">重新加载</el-button>
    </el-empty>
  </el-card>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  precheck: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['refresh'])

const router = useRouter()
const detailsCollapsed = ref(false)

watch(
  () => props.precheck,
  (value) => {
    const hasNoOutstandingIssues = Boolean(
      value &&
      value.summary.can_run &&
      value.summary.warning_issue_count === 0
    )
    detailsCollapsed.value = hasNoOutstandingIssues
  },
  { immediate: true },
)

const footerText = computed(() => {
  if (!props.precheck) {
    return '暂无检查结果。'
  }
  if (!props.precheck.summary.can_run) {
    return `当前不能开始排课，请先处理 ${props.precheck.summary.blocking_issue_count} 个阻塞项。`
  }
  if (props.precheck.summary.warning_issue_count > 0) {
    return `必需项已通过，可以试排；另有 ${props.precheck.summary.warning_issue_count} 条非阻塞提醒可按需处理。`
  }
  return '必需项已通过，可以开始试排。'
})

const averageTeacherHoursDisplay = computed(() => {
  const value = props.precheck?.summary?.average_teacher_hours
  if (value == null) {
    return '--'
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
})

const estimatedMinTeachersDisplay = computed(() => {
  const value = props.precheck?.summary?.estimated_min_teachers
  if (value == null) {
    return '--'
  }
  return String(value)
})
</script>

<style scoped>
.precheck-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
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

.section + .section {
  margin-top: 18px;
}

.collapsed-summary {
  display: grid;
  gap: 14px;
}

.collapsed-summary__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.collapsed-summary__footer {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.metrics-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.metric-item {
  padding: 14px 16px;
  border-radius: 12px;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
}

.metric-item.compact {
  background: #fafbfd;
}

.metric-label {
  font-size: 13px;
  color: #606266;
}

.metric-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 700;
  color: #303133;
}

.metric-tip {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #909399;
}

.section-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
}

.section-title.danger {
  color: #f56c6c;
}

.section-title.warning {
  color: #e6a23c;
}

.section-title.success {
  color: #67c23a;
}

.issue-item {
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid #ebeef5;
}

.issue-item + .issue-item {
  margin-top: 10px;
}

.issue-danger {
  border-color: #f8d7da;
  background: #fff8f8;
}

.issue-warning {
  border-color: #f5dab1;
  background: #fffdf7;
}

.issue-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.issue-detail {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: #606266;
}

.issue-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.passed-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.passed-item {
  padding: 12px 14px;
  border-radius: 10px;
  background: #f7fbf5;
  border: 1px solid #d9ecce;
}

.passed-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.passed-detail {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: #606266;
}

.footer-bar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.footer-summary {
  font-size: 13px;
  color: #67c23a;
}

.footer-summary.danger {
  color: #f56c6c;
}

@media (max-width: 768px) {
  .card-header,
  .footer-bar,
  .collapsed-summary__footer {
    flex-direction: column;
    align-items: stretch;
  }

  .metrics-strip,
  .collapsed-summary__metrics,
  .passed-grid {
    grid-template-columns: 1fr;
  }
}
</style>
