<template>
  <div class="page-container">
    <h2>听课分配</h2>

    <el-card class="filter-card">
      <div class="filter-row">
        <ScheduleResultPicker
          v-model="selectedResult"
          :current-result="currentResult"
          :show-activate-action="false"
          @refresh="refreshCurrent"
        />
      </div>
      <el-form :inline="true" style="margin-top: 12px;">
        <el-form-item label="同一教师最多听">
          <el-input-number v-model="maxPerTarget" :min="1" :max="6" :step="1" style="width: 100px;" />
          <span style="margin-left: 4px;">次</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="generating" :disabled="!selectedResult" @click="generate">
            生成
          </el-button>
          <el-button type="success" :disabled="!assignments.length" @click="exportToExcel">
            导出 Excel
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-alert
      v-if="warnings.length"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 20px;"
    >
      <template #title>
        以下教师分配不足 6 次听课：
      </template>
      <div>
        <span v-for="(w, i) in warnings" :key="i">
          {{ w }}<span v-if="i < warnings.length - 1">；</span>
        </span>
      </div>
    </el-alert>

    <el-card v-if="assignments.length">
      <el-table
        :data="filteredAssignments"
        stripe
        border
        :default-sort="{ prop: 'observerName', order: 'ascending' }"
        @sort-change="onSortChange"
      >
        <el-table-column prop="observerName" label="听课教师" sortable="custom" width="120"
          :filters="observerFilters" :filter-method="filterObserver" filter-placement="bottom" />
        <el-table-column prop="week" label="周次" sortable="custom" width="80"
          :filters="weekFilters" :filter-method="filterWeek" filter-placement="bottom" />
        <el-table-column prop="dayLabel" label="星期" sortable="custom" width="80"
          :filters="dayFilters" :filter-method="filterDay" filter-placement="bottom" />
        <el-table-column prop="periodLabel" label="节次" sortable="custom" width="80" />
        <el-table-column prop="targetName" label="被听课教师" sortable="custom" width="120"
          :filters="targetFilters" :filter-method="filterTarget" filter-placement="bottom" />
        <el-table-column prop="subjectName" label="科目" sortable="custom"
          :filters="subjectFilters" :filter-method="filterSubject" filter-placement="bottom" />
        <el-table-column prop="className" label="班级" sortable="custom" width="120" />
      </el-table>
    </el-card>

    <el-empty v-else-if="hasGenerated" description="暂无数据" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import * as XLSX from 'xlsx'
import { getTeacherTimetable, getActiveSchedule, getScheduleResult } from '../api/scheduler'
import { getTeachers } from '../api/teachers'
import { getTravelGroups } from '../api/resources'
import { useSchoolStore } from '../stores/school'
import ScheduleResultPicker from '../components/ScheduleResultPicker.vue'

const schoolStore = useSchoolStore()
const DAY_LABELS = computed(() => schoolStore.dayLabels)
const WEEKS = [1, 2, 3, 4]
const PERIODS_PER_DAY = computed(() => schoolStore.periodsPerDay)
const REQUIRED_COUNT = 6

const teachers = ref([])
const travelGroups = ref([])
const selectedResult = ref(null)
const currentResult = ref(null)
const maxPerTarget = ref(2)
const assignments = ref([])
const warnings = ref([])
const generating = ref(false)
const hasGenerated = ref(false)

// Sort state for custom sorting
const currentSort = ref({ prop: 'observerName', order: 'ascending' })

const onSortChange = ({ prop, order }) => {
  currentSort.value = { prop, order }
}

const filteredAssignments = computed(() => {
  const { prop, order } = currentSort.value
  if (!prop || !order) return assignments.value
  const list = [...assignments.value]
  const dir = order === 'ascending' ? 1 : -1
  list.sort((a, b) => {
    const va = a[prop]
    const vb = b[prop]
    if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir
    return String(va).localeCompare(String(vb), 'zh-CN') * dir
  })
  return list
})

// Column filters
const uniqueValues = (key) => {
  const seen = new Set()
  return assignments.value
    .map(a => a[key])
    .filter(v => { if (seen.has(v)) return false; seen.add(v); return true })
    .sort((a, b) => typeof a === 'number' ? a - b : String(a).localeCompare(String(b), 'zh-CN'))
    .map(v => ({ text: String(v), value: v }))
}

const observerFilters = computed(() => uniqueValues('observerName'))
const weekFilters = computed(() => uniqueValues('week'))
const dayFilters = computed(() => uniqueValues('dayLabel'))
const targetFilters = computed(() => uniqueValues('targetName'))
const subjectFilters = computed(() => uniqueValues('subjectName'))

const filterObserver = (value, row) => row.observerName === value
const filterWeek = (value, row) => row.week === value
const filterDay = (value, row) => row.dayLabel === value
const filterTarget = (value, row) => row.targetName === value
const filterSubject = (value, row) => row.subjectName === value

// Fisher-Yates shuffle
const shuffle = (arr) => {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
}

const generate = async () => {
  if (!selectedResult.value) return
  generating.value = true
  hasGenerated.value = true
  warnings.value = []

  try {
    // 1. Load all teacher timetables in parallel
    const timetables = await Promise.all(
      teachers.value.map(async (t) => {
        try {
          const entries = await getTeacherTimetable(selectedResult.value, t.id)
          return { teacherId: t.id, teacherName: t.name, entries }
        } catch {
          return { teacherId: t.id, teacherName: t.name, entries: [] }
        }
      })
    )

    // 2. Build teacher → dayOff mapping (travel group day_off)
    const teacherDayOff = {}  // teacherId → day (0-4) or undefined
    const groupDayOff = {}
    for (const g of travelGroups.value) {
      groupDayOff[g.id] = g.day_off
    }
    for (const t of teachers.value) {
      if (t.travel_group != null && groupDayOff[t.travel_group] != null) {
        teacherDayOff[t.teacherId ?? t.id] = groupDayOff[t.travel_group]
      }
    }

    // 3. Build global slot mapping: (day, period) → list of teaching teachers
    const slotTeachers = {}  // "day-period" → [{teacherId, teacherName, subjectName, className}]
    const teachingSlots = {} // teacherId → Set<"day-period">

    for (const tt of timetables) {
      teachingSlots[tt.teacherId] = new Set()
      for (const e of tt.entries) {
        const key = `${e.day}-${e.period}`
        teachingSlots[tt.teacherId].add(key)
        // 校本课程不纳入听课候选
        const isCombined = (e.subject_name && e.subject_name.startsWith('校本课程')) ||
          e.school_class_name === '(全年级)'
        if (isCombined) continue
        if (!slotTeachers[key]) slotTeachers[key] = []
        slotTeachers[key].push({
          teacherId: tt.teacherId,
          teacherName: tt.teacherName,
          subjectName: e.subject_name,
          className: e.school_class_name
        })
      }
    }

    // 4. For each teacher, assign observation slots
    const allAssignments = []
    const newWarnings = []

    for (const tt of timetables) {
      // a. Find free slots (not teaching, not on dayOff)
      const dayOff = teacherDayOff[tt.teacherId]
      const freeSlots = []
      for (let day = 0; day < 5; day++) {
        if (day === dayOff) continue  // skip travel group day off
        for (let period = 0; period < (PERIODS_PER_DAY.value[day] ?? 0); period++) {
          const key = `${day}-${period}`
          if (!teachingSlots[tt.teacherId].has(key)) {
            freeSlots.push({ day, period, key })
          }
        }
      }

      // b. Build candidate pool: expand to 4 weeks
      const candidates = []
      for (const slot of freeSlots) {
        const teaching = slotTeachers[slot.key]
        if (!teaching) continue
        for (const target of teaching) {
          if (target.teacherId === tt.teacherId) continue  // skip self
          for (const week of WEEKS) {
            candidates.push({
              observerId: tt.teacherId,
              observerName: tt.teacherName,
              week,
              day: slot.day,
              period: slot.period,
              dayLabel: DAY_LABELS.value[slot.day],
              periodLabel: `第${slot.period + 1}节`,
              targetId: target.teacherId,
              targetName: target.teacherName,
              subjectName: target.subjectName,
              className: target.className
            })
          }
        }
      }

      // c. Shuffle and greedily pick 6
      shuffle(candidates)
      const picked = []
      const usedSlots = new Set()  // "week-day-period"
      const targetCount = {}       // targetId → count

      for (const c of candidates) {
        if (picked.length >= REQUIRED_COUNT) break
        const slotKey = `${c.week}-${c.day}-${c.period}`
        if (usedSlots.has(slotKey)) continue
        const cnt = targetCount[c.targetId] || 0
        if (cnt >= maxPerTarget.value) continue
        usedSlots.add(slotKey)
        targetCount[c.targetId] = cnt + 1
        picked.push(c)
      }

      allAssignments.push(...picked)

      if (picked.length < REQUIRED_COUNT) {
        newWarnings.push(`${tt.teacherName}（仅分配 ${picked.length} 次）`)
      }
    }

    assignments.value = allAssignments
    warnings.value = newWarnings
  } finally {
    generating.value = false
  }
}

const exportToExcel = () => {
  const header = ['听课教师', '周次', '星期', '节次', '被听课教师', '科目', '班级']
  const rows = [header]
  for (const a of filteredAssignments.value) {
    rows.push([
      a.observerName,
      a.week,
      a.dayLabel,
      a.periodLabel,
      a.targetName,
      a.subjectName,
      a.className
    ])
  }

  const wb = XLSX.utils.book_new()
  const ws = XLSX.utils.aoa_to_sheet(rows)
  ws['!cols'] = [
    { wch: 12 }, { wch: 6 }, { wch: 6 }, { wch: 8 },
    { wch: 12 }, { wch: 12 }, { wch: 12 }
  ]
  XLSX.utils.book_append_sheet(wb, ws, '听课分配')
  XLSX.writeFile(wb, `听课分配_#${selectedResult.value}.xlsx`)
}

const reloadCurrent = async () => {
  if (!selectedResult.value) {
    currentResult.value = null
    return
  }
  try {
    currentResult.value = await getScheduleResult(selectedResult.value)
  } catch {
    currentResult.value = null
  }
}

const refreshCurrent = reloadCurrent

watch(selectedResult, reloadCurrent)

onMounted(async () => {
  const [t, g] = await Promise.all([getTeachers(), getTravelGroups()])
  teachers.value = t
  travelGroups.value = g
  try {
    const active = await getActiveSchedule()
    currentResult.value = active
    selectedResult.value = active?.id ?? null
  } catch {
    // no active result available
  }
})
</script>

<style scoped>
.page-container { background: #fff; padding: 20px; border-radius: 4px; }
.page-container h2 { margin-bottom: 20px; }
.filter-card { margin-bottom: 20px; }
.filter-row { margin-bottom: 4px; }
</style>
