import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useSchoolStore = defineStore('school', () => {
  const schools = ref([])
  const currentSchoolId = ref(null)
  const calendarConfig = ref(null)

  const currentSchool = computed(() =>
    schools.value.find(s => s.id === currentSchoolId.value) || null
  )

  const dayLabels = computed(() =>
    calendarConfig.value?.day_labels || ['周一', '周二', '周三', '周四', '周五']
  )

  const periodsPerDay = computed(() =>
    calendarConfig.value?.periods_per_day || { 0: 6, 1: 6, 2: 6, 3: 6, 4: 4 }
  )

  const dayCount = computed(() =>
    calendarConfig.value?.day_count || 5
  )

  const dayOptions = computed(() =>
    dayLabels.value.map((label, i) => ({ label, value: i }))
  )

  const fetchSchools = async () => {
    try {
      schools.value = await api.get('/schools/')
      if (!currentSchoolId.value && schools.value.length > 0) {
        currentSchoolId.value = schools.value[0].id
      }
    } catch (e) {
      console.error('获取学校列表失败:', e)
    }
  }

  const fetchCalendarConfig = async () => {
    try {
      calendarConfig.value = await api.get('/calendar-config/')
    } catch (e) {
      console.error('获取日历配置失败:', e)
      calendarConfig.value = null
    }
  }

  const setCurrentSchool = async (id) => {
    currentSchoolId.value = id
    localStorage.setItem('currentSchoolId', id)
    await fetchCalendarConfig()
  }

  const init = async () => {
    const saved = localStorage.getItem('currentSchoolId')
    if (saved) {
      currentSchoolId.value = parseInt(saved, 10)
    }
    await fetchSchools()
    if (currentSchoolId.value && !schools.value.find(s => s.id === currentSchoolId.value)) {
      currentSchoolId.value = schools.value[0]?.id || null
    }
    if (currentSchoolId.value) {
      localStorage.setItem('currentSchoolId', currentSchoolId.value)
      await fetchCalendarConfig()
    }
  }

  return {
    schools,
    currentSchoolId,
    currentSchool,
    calendarConfig,
    dayLabels,
    periodsPerDay,
    dayCount,
    dayOptions,
    fetchSchools,
    fetchCalendarConfig,
    setCurrentSchool,
    init,
  }
})
