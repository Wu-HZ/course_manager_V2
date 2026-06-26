<template>
  <div class="page-container">
    <h2>执行排课</h2>

    <SchedulePrecheckPanel
      :precheck="precheck"
      :loading="precheckLoading"
      @refresh="loadPrecheck"
    />

    <el-card class="run-card">
      <template #header>
        <div class="run-card__header">
          <div>
            <div class="run-card__title">排课参数</div>
            <div class="run-card__subtitle">普通使用只需开始排课，求解参数已收纳到高级设置。</div>
          </div>
          <el-tag :type="runStatusTagType" effect="light">{{ runStatusTagText }}</el-tag>
        </div>
      </template>

      <div class="run-overview">
        <div class="run-primary-panel" :class="{ blocked: !canRunSchedule }">
          <div class="run-primary-panel__eyebrow">开始本次排课</div>
          <div class="run-primary-panel__title">按当前数据与约束生成新的排课结果</div>
          <div class="run-primary-panel__description">{{ runPrimaryDescription }}</div>
          <div class="run-primary-panel__actions">
            <el-button
              type="primary"
              size="large"
              :loading="running"
              :disabled="!canRunSchedule"
              @click="runSchedule"
            >
              <el-icon v-if="!running"><VideoPlay /></el-icon>
              {{ running ? '排课中...' : '开始排课' }}
            </el-button>
          </div>
          <div v-if="!canRunSchedule" class="run-primary-panel__notice">
            请先处理上方必须项后再开始排课。
          </div>
        </div>

        <div class="run-side-panel">
          <div class="status-card">
            <div class="status-card__top">
              <div class="status-card__title">浏览器通知</div>
              <el-tag :type="notificationTagType" effect="light">{{ notificationTagText }}</el-tag>
            </div>
            <div class="status-card__text">{{ notificationStatusText }}</div>
            <el-button
              v-if="notificationSupported && notificationPermission !== 'granted'"
              size="small"
              plain
              @click="requestNotificationPermission"
            >
              {{ notificationPermission === 'denied' ? '查看权限设置' : '开启通知' }}
            </el-button>
          </div>

          <button type="button" class="advanced-toggle" @click="advancedExpanded = !advancedExpanded">
            <div class="advanced-toggle__main">
              <div class="advanced-toggle__title">高级设置</div>
              <div class="advanced-toggle__subtitle">如无特殊需求，保持默认即可</div>
            </div>
            <div class="advanced-toggle__summary">
              <span v-for="item in advancedSummaryItems" :key="item" class="advanced-toggle__chip">
                {{ item }}
              </span>
            </div>
            <div class="advanced-toggle__indicator">{{ advancedExpanded ? '收起' : '展开' }}</div>
          </button>
        </div>
      </div>

      <transition name="advanced-panel">
        <div v-show="advancedExpanded" class="advanced-panel">
          <div class="advanced-panel__header">
            <div class="advanced-panel__title">求解参数</div>
            <div class="advanced-panel__subtitle">
              这些参数只影响求解策略，不影响课程、教师和约束数据本身。
            </div>
          </div>
          <div class="advanced-grid">
            <div class="advanced-field">
              <div class="advanced-field__label">单次求解时限</div>
              <div class="advanced-field__hint">有解通常数秒返回；此值为放弃求解、转为无解诊断的上限（秒）。</div>
              <el-input-number v-model="timeLimit" :min="10" :max="600" />
            </div>
            <div class="advanced-field">
              <div class="advanced-field__label">求解器线程数</div>
              <div class="advanced-field__hint">并行求解线程，建议 ≥8，过低会明显变慢。</div>
              <el-input-number v-model="numWorkers" :min="1" :max="32" />
            </div>
            <div class="advanced-field">
              <div class="advanced-field__label">求解质量容限</div>
              <div class="advanced-field__hint">允许与最优的差距（%），越小越接近最优但越慢，8 通常足够。</div>
              <el-input-number v-model="gapPercent" :min="0" :max="50" />
            </div>
          </div>
        </div>
      </transition>
    </el-card>

    <el-card ref="resultCardRef" v-if="result" class="result-card" :class="resultClass">
      <template #header>排课结果</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="结果名称">
          {{ getScheduleResultDisplayName(result) }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType">{{ statusText }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="总耗时">{{ result.solve_time_ms }} ms</el-descriptions-item>
        <el-descriptions-item label="课表条目数">
          {{ result.entry_count || result.entries?.length || 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ result.created_at }}</el-descriptions-item>
        <el-descriptions-item label="自动分配" v-if="autoAssignedCount !== null">
          <el-tag type="success" size="small">{{ autoAssignedCount }} 条</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="retryStats" class="retry-stats">
        <el-divider content-position="left">重试统计</el-divider>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="尝试次数">
            <el-tag :type="retryStats.attempts === 1 ? 'success' : 'warning'" size="small">
              {{ retryStats.attempts }} 次
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="失败次数">
            <el-tag :type="retryStats.failures === 0 ? 'success' : 'info'" size="small">
              {{ retryStats.failures }} 次
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="成功率">
            <el-tag :type="retryStats.success_rate >= 50 ? 'success' : 'warning'" size="small">
              {{ retryStats.success_rate?.toFixed(1) }}%
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="retryStats.failure_reasons?.length" class="failure-reasons">
          <h5>失败原因</h5>
          <ul>
            <li v-for="(fail, i) in retryStats.failure_reasons" :key="i">
              第 {{ fail.attempt }} 次：{{ fail.reason }}
            </li>
          </ul>
        </div>
      </div>

      <div v-if="errors.length" class="errors">
        <h4>错误信息</h4>
        <ul>
          <li v-for="(err, i) in errors" :key="i">{{ err }}</li>
        </ul>
      </div>

      <div v-if="diagnostics.length" class="diagnostics">
        <el-divider />
        <h4>诊断分析</h4>
        <pre class="diagnostics-content">{{ diagnostics.join('\n') }}</pre>
      </div>

      <div class="actions" v-if="result.id">
        <el-button type="primary" @click="$router.push('/schedule-view')">查看课表</el-button>
        <el-button @click="$router.push('/assignments')">查看授课分配</el-button>
      </div>
    </el-card>

    <el-card class="history-card">
      <template #header>历史记录</template>
      <ScheduleResultPicker
        ref="pickerRef"
        inline
        :model-value="result?.id ?? null"
        :current-result="result"
        @update:model-value="onHistorySelect"
      />
    </el-card>

    <el-dialog
      v-model="completionDialogVisible"
      :title="completionDialogTitle"
      width="520px"
      :close-on-click-modal="false"
    >
      <div class="completion-dialog">
        <div class="completion-dialog__status">
          <span class="completion-dialog__label">结果状态</span>
          <el-tag :type="statusType" effect="dark">{{ statusText }}</el-tag>
        </div>
        <p class="completion-dialog__description">{{ completionDialogDescription }}</p>
        <div class="completion-dialog__meta">
          <div class="completion-dialog__meta-item">
            <span class="completion-dialog__meta-label">结果名称</span>
            <strong>{{ completionResultName }}</strong>
          </div>
          <div class="completion-dialog__meta-item">
            <span class="completion-dialog__meta-label">总耗时</span>
            <strong>{{ completionSolveTimeText }}</strong>
          </div>
          <div class="completion-dialog__meta-item" v-if="autoAssignedCount !== null">
            <span class="completion-dialog__meta-label">自动分配</span>
            <strong>{{ autoAssignedCount }} 节</strong>
          </div>
          <div class="completion-dialog__meta-item" v-if="retryStats?.attempts">
            <span class="completion-dialog__meta-label">尝试次数</span>
            <strong>{{ retryStats.attempts }} 次</strong>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="completionDialogVisible = false">
          {{ completionDialogMode === 'success' ? '稍后查看' : '关闭' }}
        </el-button>
        <el-button type="primary" @click="handleCompletionPrimaryAction">
          {{ completionDialogPrimaryText }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import SchedulePrecheckPanel from '../components/SchedulePrecheckPanel.vue'
import { getSchedulePrecheck, getScheduleResult, runSchedule as runScheduleApi } from '../api/scheduler'
import {
  getScheduleResultDisplayName,
  getScheduleResultStatusText,
  getScheduleResultStatusType,
} from '../utils/scheduleResults'
import ScheduleResultPicker from '../components/ScheduleResultPicker.vue'

const timeLimit = ref(60)
const numWorkers = ref(8)
const gapPercent = ref(8)
const advancedExpanded = ref(false)
const running = ref(false)
const result = ref(null)
const errors = ref([])
const diagnostics = ref([])
const autoAssignedCount = ref(null)
const retryStats = ref(null)
const pickerRef = ref(null)
const resultCardRef = ref(null)
const precheck = ref(null)
const precheckLoading = ref(false)
const completionDialogVisible = ref(false)
const completionDialogMode = ref('success')
const lastSolveTimeMs = ref(0)
const notificationPermission = ref('default')
const router = useRouter()
const notificationSupported = typeof window !== 'undefined' && 'Notification' in window
let activeCompletionNotification = null

const statusText = computed(() => getScheduleResultStatusText(result.value?.solve_status))
const statusType = computed(() => getScheduleResultStatusType(result.value?.solve_status))
const resultClass = computed(() => {
  const status = result.value?.solve_status
  if (status === 'INFEASIBLE' || status === 'FAILED_ALL_ATTEMPTS') {
    return 'error'
  }
  return 'success'
})
const canRunSchedule = computed(() => precheck.value?.summary.can_run ?? true)
const runStatusTagType = computed(() => (canRunSchedule.value ? 'success' : 'danger'))
const runStatusTagText = computed(() => (canRunSchedule.value ? '可以开始' : '存在阻塞项'))
const runPrimaryDescription = computed(() => {
  if (!canRunSchedule.value) {
    return '当前仍有前置必需项未处理，排课入口会保持禁用，直到这些阻塞项被解决。'
  }
  return '系统会按当前课程、教师、约束和锁定信息执行求解，并将本次结果保存到历史记录。'
})
const notificationTagType = computed(() => {
  if (!notificationSupported) {
    return 'info'
  }
  if (notificationPermission.value === 'granted') {
    return 'success'
  }
  if (notificationPermission.value === 'denied') {
    return 'danger'
  }
  return 'warning'
})
const notificationTagText = computed(() => {
  if (!notificationSupported) {
    return '不支持'
  }
  if (notificationPermission.value === 'granted') {
    return '已开启'
  }
  if (notificationPermission.value === 'denied') {
    return '已拦截'
  }
  return '未开启'
})
const advancedSummaryItems = computed(() => ([
  `时限 ${timeLimit.value} 秒`,
  `${numWorkers.value} 线程`,
  `容限 ${gapPercent.value}%`,
]))
const completionDialogTitle = computed(() => (
  completionDialogMode.value === 'success' ? '排课完成' : '排课已结束'
))
const completionDialogPrimaryText = computed(() => (
  completionDialogMode.value === 'success' ? '查看课表' : '查看结果详情'
))
const completionResultName = computed(() => {
  if (!result.value) {
    return '本次求解'
  }
  if (result.value.display_name || result.value.id) {
    return getScheduleResultDisplayName(result.value)
  }
  return '本次求解'
})
const completionSolveTimeText = computed(() => {
  const solveTimeMs = result.value?.solve_time_ms ?? lastSolveTimeMs.value
  return solveTimeMs ? `${solveTimeMs} ms` : '未返回'
})
const completionDialogDescription = computed(() => {
  const status = result.value?.solve_status
  if (completionDialogMode.value === 'success') {
    if (status === 'OPTIMAL') {
      return '已生成最优课表，可以立即进入课表查看页核对结果。'
    }
    if (status === 'FEASIBLE') {
      return '已生成可用课表，可以立即进入课表查看页继续检查。'
    }
    return '已生成排课结果，可以立即进入课表查看页查看。'
  }

  if (status === 'INFEASIBLE') {
    return '本次求解已结束，但当前约束下未找到可行课表。请查看下方错误信息和诊断分析。'
  }
  if (status === 'FAILED_ALL_ATTEMPTS') {
    return '本次求解已结束，但所有尝试都未生成可用课表。请查看失败原因和诊断分析。'
  }
  if (status === 'MODEL_INVALID') {
    return '本次求解已结束，但模型配置存在问题，未生成可用课表。请查看下方诊断信息。'
  }
  return '本次求解已结束，但未生成可用课表。请查看当前页面的结果信息。'
})
const notificationStatusText = computed(() => {
  if (!notificationSupported) {
    return '当前浏览器不支持系统通知。'
  }
  if (notificationPermission.value === 'granted') {
    return '已开启；排课结束且当前页面不在前台时，会发送浏览器通知。'
  }
  if (notificationPermission.value === 'denied') {
    return '浏览器已阻止本站通知；如需启用，请在浏览器站点权限中重新允许。'
  }
  return '未开启；建议允许通知，这样离开当前页面时也能在排课结束后收到提醒。'
})

const syncNotificationPermission = () => {
  notificationPermission.value = notificationSupported ? Notification.permission : 'unsupported'
}

const requestNotificationPermission = async ({ silent = false } = {}) => {
  if (!notificationSupported) {
    if (!silent) {
      ElMessage.warning('当前浏览器不支持系统通知')
    }
    return 'unsupported'
  }
  if (notificationPermission.value === 'denied') {
    if (!silent) {
      ElMessage.warning('浏览器已阻止通知，请在站点权限中手动允许')
    }
    return 'denied'
  }

  const permission = await Notification.requestPermission()
  notificationPermission.value = permission

  if (!silent) {
    if (permission === 'granted') {
      ElMessage.success('浏览器通知已开启')
    } else {
      ElMessage.warning('浏览器通知未开启')
    }
  }
  return permission
}

const notifyScheduleCompletion = async () => {
  if (!notificationSupported || notificationPermission.value !== 'granted') {
    return
  }
  if (document.visibilityState === 'visible' && document.hasFocus()) {
    return
  }

  activeCompletionNotification?.close()

  const notification = new Notification(completionDialogTitle.value, {
    body: completionDialogMode.value === 'success'
      ? `${statusText.value} · ${completionResultName.value} · 用时 ${completionSolveTimeText.value}`
      : `${statusText.value} · 请返回排课页查看错误信息和诊断分析。`,
    tag: 'schedule-run-completion',
    renotify: true,
    requireInteraction: true,
  })

  notification.onclick = async () => {
    window.focus()
    if (completionDialogMode.value === 'success') {
      await router.push('/schedule-view')
    } else {
      await router.push('/schedule-run')
    }
    notification.close()
  }
  notification.onclose = () => {
    if (activeCompletionNotification === notification) {
      activeCompletionNotification = null
    }
  }
  activeCompletionNotification = notification
}

const openCompletionDialog = (mode) => {
  completionDialogMode.value = mode
  completionDialogVisible.value = true
}

const scrollToResultCard = async () => {
  completionDialogVisible.value = false
  await nextTick()
  resultCardRef.value?.$el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const handleCompletionPrimaryAction = async () => {
  if (completionDialogMode.value === 'success') {
    completionDialogVisible.value = false
    await router.push('/schedule-view')
    return
  }
  await scrollToResultCard()
}

const loadPrecheck = async () => {
  precheckLoading.value = true
  try {
    precheck.value = await getSchedulePrecheck()
  } catch (error) {
    console.error('Failed to load precheck:', error)
  } finally {
    precheckLoading.value = false
  }
}

const onHistorySelect = async (id) => {
  if (!id) {
    result.value = null
    return
  }
  try {
    result.value = await getScheduleResult(id)
    errors.value = []
    diagnostics.value = []
    autoAssignedCount.value = null
    retryStats.value = null
  } catch {
    ElMessage.error('加载排课结果失败')
  }
}

const runSchedule = async () => {
  if (precheck.value && !precheck.value.summary.can_run) {
    ElMessage.error('请先处理排课前检查中的必须项')
    return
  }

  if (notificationSupported && notificationPermission.value === 'default') {
    await requestNotificationPermission({ silent: true })
  }

  running.value = true
  completionDialogVisible.value = false
  result.value = null
  errors.value = []
  diagnostics.value = []
  autoAssignedCount.value = null
  retryStats.value = null
  lastSolveTimeMs.value = 0

  try {
    const res = await runScheduleApi({
      timeLimit: timeLimit.value,
      numWorkers: numWorkers.value,
      gap: gapPercent.value,
    })
    result.value = res.result
    autoAssignedCount.value = res.auto_assigned_count || 0
    retryStats.value = res.retry_stats || null
    lastSolveTimeMs.value = res.solve_time_ms || res.result?.solve_time_ms || 0
    if (!res.success) {
      errors.value = res.errors || []
      diagnostics.value = res.diagnostics || []
    }
    ElMessage.success('排课完成')
    openCompletionDialog(res.success === false ? 'failure' : 'success')
    await notifyScheduleCompletion()
    pickerRef.value?.refresh()
  } catch (error) {
    if (error.response?.data) {
      result.value = error.response.data.result || { solve_status: error.response.data.status }
      errors.value = error.response.data.errors || []
      diagnostics.value = error.response.data.diagnostics || []
      autoAssignedCount.value = error.response.data.auto_assigned_count || null
      retryStats.value = error.response.data.retry_stats || null
      lastSolveTimeMs.value = error.response.data.solve_time_ms || 0
      ElMessage.error('排课失败')
      openCompletionDialog('failure')
      await notifyScheduleCompletion()
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      errors.value = ['请求超时，请稍后刷新页面查看历史记录。']
      ElMessage.error('请求超时，后台可能仍在计算')
    } else {
      errors.value = [error.message || '未知错误']
      ElMessage.error(`排课失败: ${error.message || '未知错误'}`)
    }
  } finally {
    running.value = false
    pickerRef.value?.refresh()
    await loadPrecheck()
  }
}

onMounted(() => {
  syncNotificationPermission()
  loadPrecheck()
})

onBeforeUnmount(() => {
  activeCompletionNotification?.close()
})
</script>

<style scoped>
.page-container {
  background: #fff;
  padding: 20px;
  border-radius: 4px;
}

.page-container h2 {
  margin-bottom: 20px;
}

.run-card,
.result-card,
.history-card {
  margin-bottom: 20px;
}

.run-card__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.run-card__title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.run-card__subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.run-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(300px, 1fr);
  gap: 16px;
}

.run-primary-panel {
  padding: 24px;
  border: 1px solid #d7e8fb;
  border-radius: 18px;
  background: linear-gradient(135deg, #f7fbff 0%, #eef4ff 100%);
}

.run-primary-panel.blocked {
  border-color: #f3c8cd;
  background: linear-gradient(135deg, #fff8f8 0%, #fff1f1 100%);
}

.run-primary-panel__eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #7b8ba1;
  text-transform: uppercase;
}

.run-primary-panel__title {
  margin-top: 10px;
  font-size: 24px;
  font-weight: 600;
  line-height: 1.4;
  color: #1f2d3d;
}

.run-primary-panel__description {
  margin-top: 10px;
  max-width: 560px;
  font-size: 14px;
  line-height: 1.8;
  color: #526277;
}

.run-primary-panel__actions {
  margin-top: 20px;
}

.run-primary-panel__notice {
  margin-top: 14px;
  font-size: 13px;
  line-height: 1.7;
  color: #d14a5c;
}

.run-side-panel {
  display: grid;
  gap: 16px;
}

.status-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px;
  border: 1px solid #e7edf4;
  border-radius: 18px;
  background: #fff;
}

.status-card__top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.status-card__title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.status-card__text {
  font-size: 13px;
  line-height: 1.7;
  color: #606266;
}

.advanced-toggle {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px;
  border: 1px solid #e4ebf3;
  border-radius: 18px;
  background: #f8fafc;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.advanced-toggle:hover {
  border-color: #cad9ea;
  background: #f3f7fb;
}

.advanced-toggle__main {
  min-width: 0;
}

.advanced-toggle__title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.advanced-toggle__subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.advanced-toggle__summary {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.advanced-toggle__chip {
  padding: 5px 10px;
  border: 1px solid #dce6ef;
  border-radius: 999px;
  background: #fff;
  font-size: 12px;
  line-height: 1.4;
  color: #5a6b80;
}

.advanced-toggle__indicator {
  font-size: 13px;
  font-weight: 600;
  line-height: 30px;
  color: #409eff;
  white-space: nowrap;
}

.advanced-panel {
  margin-top: 16px;
  padding: 18px;
  border: 1px solid #e8eef5;
  border-radius: 18px;
  background: #fbfcfe;
}

.advanced-panel__header {
  margin-bottom: 16px;
}

.advanced-panel__title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.advanced-panel__subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.advanced-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.advanced-field {
  padding: 16px;
  border: 1px solid #e7edf4;
  border-radius: 14px;
  background: #fff;
}

.advanced-field__label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.advanced-field__hint {
  margin: 6px 0 14px;
  font-size: 12px;
  line-height: 1.6;
  color: #606266;
}

.advanced-field :deep(.el-input-number) {
  width: 100%;
}

.result-card.error {
  border-color: #f56c6c;
}

.result-card.success {
  border-color: #67c23a;
}

.errors {
  margin-top: 20px;
  color: #f56c6c;
}

.errors h4,
.diagnostics h4 {
  margin-bottom: 10px;
}

.diagnostics {
  margin-top: 10px;
}

.diagnostics h4 {
  color: #409eff;
}

.diagnostics-content {
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

.actions {
  margin-top: 20px;
}

.retry-stats {
  margin-top: 15px;
}

.failure-reasons {
  margin-top: 10px;
  padding: 10px;
  background: #fef0f0;
  border-radius: 4px;
  font-size: 13px;
}

.failure-reasons h5 {
  margin: 0 0 8px 0;
  color: #f56c6c;
}

.failure-reasons ul {
  margin: 0;
  padding-left: 20px;
}

.failure-reasons li {
  margin-bottom: 4px;
  color: #606266;
}

.completion-dialog__status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.completion-dialog__label,
.completion-dialog__meta-label {
  color: #909399;
  font-size: 13px;
}

.completion-dialog__description {
  margin: 16px 0;
  color: #303133;
  line-height: 1.7;
}

.completion-dialog__meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.completion-dialog__meta-item {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}

.completion-dialog__meta-item strong {
  display: block;
  margin-top: 6px;
  color: #303133;
  line-height: 1.5;
}

.advanced-panel-enter-active,
.advanced-panel-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.advanced-panel-enter-from,
.advanced-panel-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 992px) {
  .run-overview {
    grid-template-columns: 1fr;
  }

  .advanced-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .run-card__header,
  .status-card__top,
  .advanced-toggle {
    flex-direction: column;
  }

  .run-primary-panel,
  .status-card,
  .advanced-toggle,
  .advanced-panel {
    padding: 16px;
  }

  .run-primary-panel__title {
    font-size: 20px;
  }

  .advanced-toggle__summary {
    justify-content: flex-start;
  }
}
</style>
