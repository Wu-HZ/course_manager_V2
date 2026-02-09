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
        <span>校本课程分组分配</span>
      </template>
      <el-table :data="combinedAssignmentsList" stripe border>
        <el-table-column prop="groupName" label="分组名称" width="150" />
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
import TimetableGrid from '../components/TimetableGrid.vue'
import { getScheduleResults, getClassTimetable, getTeacherTimetable } from '../api/scheduler'
import { getClasses } from '../api/classes'
import { getTeachers } from '../api/teachers'

const results = ref([])
const classes = ref([])
const teachers = ref([])
const selectedResult = ref(null)
const viewType = ref('class')
const allTimetables = ref([])
const combinedAssignments = ref({})

const targets = computed(() => viewType.value === 'class' ? classes.value : teachers.value)

// 转换为表格数据格式
const combinedAssignmentsList = computed(() => {
  return Object.entries(combinedAssignments.value).map(([groupName, teacherList]) => ({
    groupName,
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
    } else if (e.teacher === null || e.teacher_name === null) {
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
