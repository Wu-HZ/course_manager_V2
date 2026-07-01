<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>课表查看</h2>
        <p class="page-subtitle">手机端默认聚焦单个课表，可按对象切换；桌面端继续支持批量纵览。</p>
      </div>
    </div>

    <el-card class="filter-card">
      <div class="filter-row">
        <ScheduleResultPicker
          v-model="selectedResult"
          :current-result="currentResult"
          @refresh="onPickerRefresh"
        />
      </div>

      <el-form :inline="!isMobile" class="filter-form">
        <el-form-item label="查看方式">
          <el-radio-group v-model="viewType" @change="loadAllTimetables">
            <el-radio-button value="class">按班级</el-radio-button>
            <el-radio-button value="teacher">按教师</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="isMobile && mobileTargetOptions.length" label="当前对象">
          <el-select v-model="selectedTargetId" placeholder="请选择课表对象">
            <el-option
              v-for="item in mobileTargetOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item>
          <div class="filter-actions">
            <el-button type="success" :disabled="!allTimetables.length" @click="exportToExcel">
              导出 Excel
            </el-button>
            <el-button type="primary" :disabled="!allTimetables.length" @click="exportToJSON">
              导出数据 (JSON)
            </el-button>
            <el-button type="warning" :disabled="!allTimetables.length" @click="showWordDialog">
              导出 Word
            </el-button>
          </div>
        </el-form-item>
      </el-form>

      <div v-if="isMobile && displayedTimetables.length" class="filter-tip">
        当前仅展示 1 个课表，可切换对象快速查看。
      </div>
    </el-card>

    <el-card v-if="viewType === 'teacher' && allTimetables.length" class="chart-card">
      <template #header>
        <div class="section-header-inline">
          <span>教师课时分布</span>
          <el-button v-if="isMobile" text @click="chartExpanded = !chartExpanded">
            {{ chartExpanded ? '收起' : '展开' }}
          </el-button>
        </div>
      </template>

      <v-chart
        v-if="!isMobile || chartExpanded"
        :option="teacherChartOption"
        :style="{ height: isMobile ? '260px' : '300px', cursor: 'pointer' }"
        autoresize
        @click="onChartClick"
      />

      <div v-else class="chart-card__tip">
        手机端默认折叠统计图，展开后可点击柱状图定位到对应教师课表。
      </div>
    </el-card>

    <template v-if="displayedTimetables.length">
      <el-card
        v-for="item in displayedTimetables"
        :key="item.id"
        :ref="el => setTimetableRef(item.id, el)"
        class="timetable-card"
      >
        <template #header>
          <div class="timetable-header">
            <span>{{ item.name }} 课表</span>
            <span class="weekly-hours">
              周课时 {{ item.stats.total }}
              （普通课程 {{ item.stats.normal }} + 校本课程 {{ item.stats.combined }} + 班会课 {{ item.stats.meeting }}）
            </span>
          </div>
        </template>
        <TimetableGrid
          :entries="item.entries"
          :show-teacher="viewType === 'class'"
          :show-class="viewType === 'teacher'"
        />
      </el-card>
    </template>

    <el-empty v-else-if="selectedResult" description="暂无数据" />

    <el-card v-if="combinedAssignments && Object.keys(combinedAssignments).length" class="combined-card">
      <template #header>
        <span>校本课程教师分组</span>
      </template>
      <div class="responsive-table-wrapper">
        <el-table :data="combinedAssignmentsList" stripe border>
          <el-table-column prop="groupName" label="分组" width="120" />
          <el-table-column label="周二">
            <template #default="{ row }">
              <el-tag v-for="t in row.tuesday" :key="t" class="table-tag">{{ t }}</el-tag>
              <span v-if="!row.tuesday.length" class="table-empty">-</span>
            </template>
          </el-table-column>
          <el-table-column label="周四">
            <template #default="{ row }">
              <el-tag v-for="t in row.thursday" :key="t" class="table-tag">{{ t }}</el-tag>
              <span v-if="!row.thursday.length" class="table-empty">-</span>
            </template>
          </el-table-column>
          <el-table-column label="合计" width="80" align="center">
            <template #default="{ row }">
              {{ row.tuesday.length + row.thursday.length }}
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-card v-if="travelGroupList.length" class="combined-card">
      <template #header>
        <span>送教分组</span>
      </template>
      <div class="responsive-table-wrapper">
        <el-table :data="travelGroupList" stripe border>
          <el-table-column prop="name" label="分组" width="120" />
          <el-table-column prop="dayOffDisplay" label="禁排日" width="100" />
          <el-table-column label="教师">
            <template #default="{ row }">
              <el-tag v-for="t in row.teachers" :key="t" class="table-tag">{{ t }}</el-tag>
              <span v-if="!row.teachers.length" class="table-empty">-</span>
            </template>
          </el-table-column>
          <el-table-column label="人数" width="80" align="center">
            <template #default="{ row }">
              {{ row.teachers.length }}
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-dialog
      v-model="wordDialogVisible"
      title="导出课表 Word"
      :fullscreen="isMobile"
      :width="isMobile ? undefined : '480px'"
      class="responsive-dialog"
    >
      <el-form :label-position="isMobile ? 'top' : 'right'" label-width="80px">
        <el-form-item label="导出类型">
          <el-checkbox-group v-model="exportTypes">
            <el-checkbox value="class">班级课表</el-checkbox>
            <el-checkbox value="teacher">教师课表</el-checkbox>
            <el-checkbox value="groups">分组信息</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="合并文件">
          <el-tooltip content="勾选后将所有类型的课表合并到同一个 docx 文件中" placement="top">
            <el-checkbox v-model="exportMerge">合并为一个文件</el-checkbox>
          </el-tooltip>
        </el-form-item>
        <el-form-item label="学校名称">
          <el-input v-model="wordSettings.school_name" placeholder="如：某某某学校" />
        </el-form-item>
        <el-form-item label="学期">
          <el-input v-model="wordSettings.semester" placeholder="如：2025年下学期" />
        </el-form-item>
        <el-form-item label="落款">
          <el-input v-model="wordSettings.footer" placeholder="如：教导处" />
        </el-form-item>
        <el-form-item label="日期">
          <el-input v-model="wordSettings.date" placeholder="如：2025年8月" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="wordDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="wordExporting" :disabled="!exportTypes.length" @click="exportToWord">
            导出
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-backtop :right="40" :bottom="40" :visibility-height="200" />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import TimetableGrid from '../components/TimetableGrid.vue'
import ScheduleResultPicker from '../components/ScheduleResultPicker.vue'
import { useResponsive } from '../composables/useResponsive'
import {
  getClassTimetable,
  getTeacherTimetable,
  getActiveSchedule,
  getScheduleResult,
  exportWord
} from '../api/scheduler'
import { getClasses } from '../api/classes'
import { getTeachers } from '../api/teachers'
import { getTravelGroups, getAssignments } from '../api/resources'
import { getSubjects } from '../api/subjects'
import { buildScheduleResultFileLabel } from '../utils/scheduleResults'
import { useSchoolStore } from '../stores/school'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const classes = ref([])
const teachers = ref([])
const selectedResult = ref(null)
const currentResult = ref(null)
const viewType = ref('class')
const allTimetables = ref([])
const travelGroups = ref([])
const selectedTargetId = ref(null)
const chartExpanded = ref(false)
const timetableRefs = {}

// Word 导出相关
const WORD_SETTINGS_KEY = 'word_export_settings'
const wordDialogVisible = ref(false)
const wordExporting = ref(false)
const exportTypes = ref(['class'])
const exportMerge = ref(false)
const wordSettings = ref(loadWordSettings())

function loadWordSettings() {
  try {
    const raw = localStorage.getItem(WORD_SETTINGS_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return { school_name: '', semester: '', footer: '教导处', date: '' }
}

function saveWordSettings() {
  try {
    localStorage.setItem(WORD_SETTINGS_KEY, JSON.stringify(wordSettings.value))
  } catch { /* ignore */ }
}

function showWordDialog() {
  wordSettings.value = loadWordSettings()
  wordDialogVisible.value = true
}

async function exportToWord() {
  if (!exportTypes.value.length) {
    ElMessage.warning('请至少选择一种导出类型')
    return
  }
  saveWordSettings()
  wordExporting.value = true
  try {
    const merge = exportMerge.value || exportTypes.value.length === 1
    const response = await exportWord({
      result_id: selectedResult.value,
      view_types: exportTypes.value,
      merge,
      ...wordSettings.value
    })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    const fileLabel = buildScheduleResultFileLabel(
      currentResult.value,
      `课表_${selectedResult.value}`
    )
    const typeLabelMap = { class: '按班级', teacher: '按教师', groups: '分组信息' }
    const typeLabel = exportTypes.value.map(t => typeLabelMap[t] || t).join('_')
    if (!merge) {
      link.download = `${fileLabel}.zip`
    } else {
      link.download = `${fileLabel}_${typeLabel}.docx`
    }
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
    wordDialogVisible.value = false
  } catch {
    ElMessage.error('导出失败')
  } finally {
    wordExporting.value = false
  }
}

const { isMobile } = useResponsive()

const setTimetableRef = (id, el) => {
  if (el) {
    timetableRefs[id] = el
  } else {
    delete timetableRefs[id]
  }
}

const targets = computed(() => (
  viewType.value === 'class' ? classes.value : teachers.value
))

const mobileTargetOptions = computed(() => targets.value.map(item => ({
  id: item.id,
  name: item.name
})))

const displayedTimetables = computed(() => {
  if (!isMobile.value) {
    return allTimetables.value
  }
  if (!selectedTargetId.value) {
    return allTimetables.value.slice(0, 1)
  }
  return allTimetables.value.filter(item => item.id === selectedTargetId.value)
})

const combinedAssignments = computed(() => currentResult.value?.combined_class_assignments || {})

const sortedTimetables = computed(() => (
  [...allTimetables.value].sort((a, b) => b.stats.total - a.stats.total)
))

const teacherChartOption = computed(() => {
  const sorted = sortedTimetables.value
  const compact = isMobile.value

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const data = params[0]
        const item = sorted[data.dataIndex]
        return `${item.name}<br/>
          普通课程: ${item.stats.normal} 节<br/>
          校本课程: ${item.stats.combined} 节<br/>
          班会课: ${item.stats.meeting} 节<br/>
          <strong>合计: ${item.stats.total} 节</strong>`
      }
    },
    grid: {
      left: compact ? '8%' : '3%',
      right: compact ? '6%' : '4%',
      bottom: compact ? '16%' : '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: sorted.map(t => t.name),
      axisLabel: {
        rotate: compact ? 45 : 30,
        fontSize: compact ? 10 : 12
      }
    },
    yAxis: {
      type: 'value',
      name: '课时数',
      minInterval: 1
    },
    series: [
      {
        name: '普通课程',
        type: 'bar',
        stack: 'total',
        data: sorted.map(t => t.stats.normal),
        itemStyle: { color: '#409eff' }
      },
      {
        name: '校本课程',
        type: 'bar',
        stack: 'total',
        data: sorted.map(t => t.stats.combined),
        itemStyle: { color: '#67c23a' }
      },
      {
        name: '班会课',
        type: 'bar',
        stack: 'total',
        data: sorted.map(t => t.stats.meeting),
        itemStyle: { color: '#e6a23c' },
        label: {
          show: !compact,
          position: 'top',
          formatter: (params) => sorted[params.dataIndex].stats.total,
          fontSize: 12,
          color: '#606266'
        }
      }
    ],
    legend: {
      data: ['普通课程', '校本课程', '班会课'],
      top: 0
    }
  }
})

const onChartClick = async (params) => {
  const sorted = sortedTimetables.value
  const item = sorted[params.dataIndex]
  if (!item) return

  if (isMobile.value) {
    selectedTargetId.value = item.id
    await nextTick()
  }

  const el = timetableRefs[item.id]
  if (el?.$el) {
    el.$el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

const combinedAssignmentsList = computed(() => {
  return Object.entries(combinedAssignments.value).map(([groupName, dayData]) => {
    if (typeof dayData === 'object' && !Array.isArray(dayData)) {
      return {
        groupName,
        tuesday: dayData['周二'] || [],
        thursday: dayData['周四'] || []
      }
    }
    return {
      groupName,
      tuesday: dayData || [],
      thursday: []
    }
  })
})

const travelGroupList = computed(() => {
  const teachersByGroup = {}
  for (const t of teachers.value) {
    if (t.travel_group) {
      if (!teachersByGroup[t.travel_group]) {
        teachersByGroup[t.travel_group] = []
      }
      teachersByGroup[t.travel_group].push(t.name)
    }
  }
  return travelGroups.value.map(g => ({
    name: g.name,
    dayOffDisplay: g.day_off_display,
    teachers: teachersByGroup[g.id] || []
  }))
})

const calcStats = (entries) => {
  const total = entries.length
  let meeting = 0
  let combined = 0

  for (const e of entries) {
    if (e.day === 4 && e.period === 3) {
      meeting++
    } else if (
      e.teacher === null ||
      e.teacher_name === null ||
      (e.subject_name && e.subject_name.startsWith('校本课程')) ||
      e.school_class_name === '(全年级)'
    ) {
      combined++
    }
  }

  const normal = total - meeting - combined
  return { total, normal, combined, meeting }
}

const loadData = async () => {
  const [classList, teacherList, travelGroupListData] = await Promise.all([
    getClasses(),
    getTeachers(),
    getTravelGroups()
  ])
  classes.value = classList
  teachers.value = teacherList
  travelGroups.value = travelGroupListData

  try {
    const active = await getActiveSchedule()
    currentResult.value = active
    selectedResult.value = active?.id ?? null
  } catch {
    currentResult.value = null
    selectedResult.value = null
  }
}

const loadCurrentResult = async (id) => {
  if (!id) {
    currentResult.value = null
    return
  }
  try {
    currentResult.value = await getScheduleResult(id)
  } catch {
    currentResult.value = null
  }
}

const onPickerRefresh = async () => {
  if (selectedResult.value) {
    await loadCurrentResult(selectedResult.value)
  }
}

watch(targets, (list) => {
  if (!list.length) {
    selectedTargetId.value = null
    return
  }
  if (!list.some(item => item.id === selectedTargetId.value)) {
    selectedTargetId.value = list[0].id
  }
}, { immediate: true })

watch(viewType, () => {
  chartExpanded.value = false
})

watch(selectedResult, async (nextId, prevId) => {
  if (nextId === prevId) return
  await loadCurrentResult(nextId)
  await loadAllTimetables()
})

const loadAllTimetables = async () => {
  if (!selectedResult.value) {
    allTimetables.value = []
    return
  }

  const targetList = targets.value
  const fetchFn = viewType.value === 'class' ? getClassTimetable : getTeacherTimetable

  const promises = targetList.map(async (target) => {
    try {
      const entries = await fetchFn(selectedResult.value, target.id)
      return {
        id: target.id,
        name: target.name,
        entries,
        stats: calcStats(entries)
      }
    } catch {
      return {
        id: target.id,
        name: target.name,
        entries: [],
        stats: { total: 0, normal: 0, combined: 0, meeting: 0 }
      }
    }
  })

  allTimetables.value = await Promise.all(promises)
  if (!allTimetables.value.some(item => item.id === selectedTargetId.value)) {
    selectedTargetId.value = allTimetables.value[0]?.id ?? null
  }
}

const exportToExcel = () => {
  const wb = XLSX.utils.book_new()
  const schoolStore = useSchoolStore()
  const dayLabels = schoolStore.dayLabels
  const periodsPerDay = schoolStore.periodsPerDay
  const maxPeriods = Math.max(...Object.values(periodsPerDay), 6)
  const dayCount = schoolStore.dayCount
  const header = ['']
  for (let p = 1; p <= maxPeriods; p++) {
    header.push(`第${p}节`)
  }

  for (const item of allTimetables.value) {
    const entryMap = {}
    for (const e of item.entries) {
      entryMap[`${e.day}-${e.period}`] = e
    }

    const rows = [header]
    for (let day = 0; day < dayCount; day++) {
      const row = [dayLabels[day] || `第${day + 1}天`]
      for (let period = 0; period < maxPeriods; period++) {
        const entry = entryMap[`${day}-${period}`]
        if (entry) {
          const line1 = entry.subject_name || ''
          const line2 = viewType.value === 'class'
            ? (entry.teacher_name || '')
            : (entry.school_class_name || '')
          row.push(line2 ? `${line1}\n${line2}` : line1)
        } else if (period >= (periodsPerDay[day] ?? 0)) {
          row.push('-')
        } else {
          row.push('')
        }
      }
      rows.push(row)
    }

    const ws = XLSX.utils.aoa_to_sheet(rows)
    ws['!cols'] = [
      { wch: 6 },
      ...Array(maxPeriods).fill({ wch: 14 })
    ]
    const sheetName = item.name.substring(0, 31)
    XLSX.utils.book_append_sheet(wb, ws, sheetName)
  }

  const viewLabel = viewType.value === 'class' ? '按班级' : '按教师'
  const fileLabel = buildScheduleResultFileLabel(currentResult.value, `课表_${selectedResult.value}`)
  XLSX.writeFile(wb, `${fileLabel}_${viewLabel}.xlsx`)
}

const exportToJSON = async () => {
  const [subjects, assignments] = await Promise.all([
    getSubjects(),
    getAssignments()
  ])

  const classTimetables = viewType.value === 'class'
    ? allTimetables.value
    : await Promise.all(
        classes.value.map(async (c) => {
          try {
            const entries = await getClassTimetable(selectedResult.value, c.id)
            return { id: c.id, name: c.name, entries }
          } catch {
            return { id: c.id, name: c.name, entries: [] }
          }
        })
      )

  const allEntries = []
  const seen = new Set()
  for (const timetable of classTimetables) {
    for (const entry of timetable.entries) {
      const key = `${entry.day}-${entry.period}-${entry.school_class ?? timetable.id}`
      if (!seen.has(key)) {
        seen.add(key)
        allEntries.push({
          day: entry.day,
          period: entry.period,
          classId: entry.school_class,
          className: entry.school_class_name,
          teacherId: entry.teacher,
          teacherName: entry.teacher_name,
          subjectId: entry.subject,
          subjectName: entry.subject_name,
          isLocked: entry.is_locked || false
        })
      }
    }
  }

  const data = {
    version: 1,
    exportedAt: new Date().toISOString(),
    resultId: selectedResult.value,
    classes: classes.value.map(c => ({
      id: c.id,
      name: c.name,
      grade: c.grade,
      homeroomTeacherId: c.homeroom_teacher,
      homeroomTeacherName: c.homeroom_teacher_name
    })),
    teachers: teachers.value.map(t => ({
      id: t.id,
      name: t.name,
      travelGroup: t.travel_group,
      travelGroupName: t.travel_group_name,
      combinedClassGroup: t.combined_class_group,
      combinedClassGroupName: t.combined_class_group_name,
      combinedClassDay: t.combined_class_day,
      excludeFromCombined: t.exclude_from_combined,
      minWeeklyHours: t.min_weekly_hours,
      maxWeeklyHours: t.max_weekly_hours
    })),
    subjects: subjects.map(s => ({
      id: s.id,
      name: s.name,
      weeklyHours: s.weekly_hours,
      isAmPreferred: s.is_am_preferred,
      allowConsecutive: s.allow_consecutive,
      maxDailyLimit: s.max_daily_limit,
      locationType: s.location_type,
      isCombinedClass: s.is_combined_class,
      applicableGrades: s.applicable_grades,
      avoidFirstPeriod: s.avoid_first_period,
      isMainSubject: s.is_main_subject,
      maxTeacherClasses: s.max_teacher_classes
    })),
    assignments: assignments.map(a => ({
      id: a.id,
      classId: a.school_class,
      className: a.school_class_name,
      subjectId: a.subject,
      subjectName: a.subject_name,
      teacherId: a.teacher,
      teacherName: a.teacher_name
    })),
    travelGroups: travelGroups.value.map(g => ({
      id: g.id,
      name: g.name,
      dayOff: g.day_off,
      dayOffDisplay: g.day_off_display
    })),
    combinedAssignments: combinedAssignments.value,
    entries: allEntries
  }

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  const fileLabel = buildScheduleResultFileLabel(currentResult.value, `课表_${selectedResult.value}`)
  link.download = `课表数据_${fileLabel}.json`
  link.click()
  URL.revokeObjectURL(url)
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
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
}

.page-subtitle {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.7;
  color: #606266;
}

.filter-card,
.chart-card {
  margin-bottom: 20px;
}

.timetable-card,
.combined-card {
  margin-top: 20px;
}

.filter-form {
  margin-top: 12px;
}

.filter-row {
  margin-bottom: 4px;
}

.filter-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-tip {
  margin-top: 12px;
  font-size: 13px;
  line-height: 1.6;
  color: #909399;
}

.section-header-inline,
.timetable-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.weekly-hours {
  font-size: 14px;
  color: #606266;
  font-weight: normal;
}

.chart-card__tip {
  font-size: 13px;
  line-height: 1.7;
  color: #606266;
}

.table-tag {
  margin-right: 6px;
  margin-bottom: 6px;
}

.table-empty {
  color: #909399;
}

@media (max-width: 768px) {
  .page-container {
    padding: 16px;
  }

  .filter-form :deep(.el-form-item) {
    width: 100%;
    margin-right: 0;
  }

  .filter-form :deep(.el-form-item__content) {
    width: 100%;
  }

  .filter-form :deep(.el-radio-group) {
    display: flex;
    width: 100%;
  }

  .filter-form :deep(.el-radio-button) {
    flex: 1;
  }

  .filter-actions,
  .section-header-inline,
  .timetable-header {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-actions :deep(.el-button) {
    margin-left: 0;
  }
}
</style>
