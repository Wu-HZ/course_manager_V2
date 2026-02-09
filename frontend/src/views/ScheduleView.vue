<template>
  <div class="page-container">
    <h2>课表查看</h2>

    <el-card class="filter-card">
      <el-form :inline="true">
        <el-form-item label="排课结果">
          <el-select v-model="selectedResult" placeholder="选择排课结果" @change="onResultChange">
            <el-option
              v-for="r in results"
              :key="r.id"
              :label="`#${r.id} - ${r.created_at} (${r.solve_status})`"
              :value="r.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="查看方式">
          <el-radio-group v-model="viewType" @change="loadAllTimetables">
            <el-radio-button value="class">按班级</el-radio-button>
            <el-radio-button value="teacher">按教师</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 教师课时柱状图 -->
    <el-card v-if="viewType === 'teacher' && allTimetables.length" class="chart-card">
      <template #header>
        <span>教师课时分布</span>
      </template>
      <v-chart :option="teacherChartOption" style="height: 300px;" autoresize />
    </el-card>

    <!-- 所有课表 -->
    <template v-if="allTimetables.length">
      <el-card v-for="item in allTimetables" :key="item.id" class="timetable-card">
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

    <!-- 校本课程分组分配表 -->
    <el-card v-if="combinedAssignments && Object.keys(combinedAssignments).length" class="combined-card">
      <template #header>
        <span>校本课程教师分组</span>
      </template>
      <el-table :data="combinedAssignmentsList" stripe border>
        <el-table-column prop="groupName" label="分组" width="120" />
        <el-table-column prop="dayLabel" label="上课日期" width="120" />
        <el-table-column prop="teachers" label="分配教师">
          <template #default="{ row }">
            <el-tag v-for="t in row.teachers" :key="t" style="margin-right: 5px;">{{ t }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="count" label="人数" width="80" align="center" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import TimetableGrid from '../components/TimetableGrid.vue'
import { getScheduleResults, getClassTimetable, getTeacherTimetable } from '../api/scheduler'
import { getClasses } from '../api/classes'
import { getTeachers } from '../api/teachers'

// 注册 ECharts 组件
use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const results = ref([])
const classes = ref([])
const teachers = ref([])
const selectedResult = ref(null)
const viewType = ref('class')
const allTimetables = ref([])
const combinedAssignments = ref({})

const targets = computed(() => viewType.value === 'class' ? classes.value : teachers.value)

// 教师课时柱状图配置
const teacherChartOption = computed(() => {
  // 按课时量从大到小排序
  const sorted = [...allTimetables.value].sort((a, b) => b.stats.total - a.stats.total)

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
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: sorted.map(t => t.name),
      axisLabel: {
        rotate: 30,
        fontSize: 12
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
        itemStyle: { color: '#e6a23c' }
      }
    ],
    legend: {
      data: ['普通课程', '校本课程', '班会课'],
      top: 0
    }
  }
})

// 转换为表格数据格式
const combinedAssignmentsList = computed(() => {
  const dayLabels = {
    '周二组': '周二下午',
    '周四组': '周四下午'
  }
  return Object.entries(combinedAssignments.value).map(([groupName, teacherList]) => ({
    groupName,
    dayLabel: dayLabels[groupName] || groupName,
    teachers: teacherList,
    count: teacherList.length
  }))
})

// 计算单个课表的周课时统计
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
      e.subject_name === '校本课程' ||
      e.school_class_name === '(全年级)'
    ) {
      combined++
    }
  }

  const normal = total - meeting - combined
  return { total, normal, combined, meeting }
}

const loadData = async () => {
  [results.value, classes.value, teachers.value] = await Promise.all([
    getScheduleResults(), getClasses(), getTeachers()
  ])
  // 自动选择最新激活的结果
  const active = results.value.find(r => r.is_active)
  if (active) {
    selectedResult.value = active.id
    combinedAssignments.value = active.combined_class_assignments || {}
  } else if (results.value.length) {
    selectedResult.value = results.value[0].id
    combinedAssignments.value = results.value[0].combined_class_assignments || {}
  }
}

const onResultChange = () => {
  const result = results.value.find(r => r.id === selectedResult.value)
  combinedAssignments.value = result?.combined_class_assignments || {}
  loadAllTimetables()
}

const loadAllTimetables = async () => {
  if (!selectedResult.value) {
    allTimetables.value = []
    return
  }

  const targetList = targets.value
  const fetchFn = viewType.value === 'class' ? getClassTimetable : getTeacherTimetable

  // 并行加载所有课表
  const promises = targetList.map(async (t) => {
    try {
      const entries = await fetchFn(selectedResult.value, t.id)
      return {
        id: t.id,
        name: t.name,
        entries,
        stats: calcStats(entries)
      }
    } catch (e) {
      return {
        id: t.id,
        name: t.name,
        entries: [],
        stats: { total: 0, normal: 0, combined: 0, meeting: 0 }
      }
    }
  })

  allTimetables.value = await Promise.all(promises)
}

onMounted(async () => {
  await loadData()
  if (selectedResult.value) {
    loadAllTimetables()
  }
})
</script>

<style scoped>
.page-container { background: #fff; padding: 20px; border-radius: 4px; }
.page-container h2 { margin-bottom: 20px; }
.filter-card { margin-bottom: 20px; }
.chart-card { margin-bottom: 20px; }
.timetable-card { margin-top: 20px; }
.combined-card { margin-top: 20px; }
.timetable-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.weekly-hours {
  font-size: 14px;
  color: #606266;
  font-weight: normal;
}
</style>
