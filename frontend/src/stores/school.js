import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useSchoolStore = defineStore('school', () => {
  const schools = ref([])
  const currentSchoolId = ref(null)

  const currentSchool = computed(() =>
    schools.value.find(s => s.id === currentSchoolId.value) || null
  )

  const fetchSchools = async () => {
    try {
      schools.value = await api.get('/schools/')
      // 如果还没有选学校，自动选第一个
      if (!currentSchoolId.value && schools.value.length > 0) {
        currentSchoolId.value = schools.value[0].id
      }
    } catch (e) {
      console.error('获取学校列表失败:', e)
    }
  }

  const setCurrentSchool = (id) => {
    currentSchoolId.value = id
    localStorage.setItem('currentSchoolId', id)
  }

  const init = async () => {
    // 恢复上次选择的学校
    const saved = localStorage.getItem('currentSchoolId')
    if (saved) {
      currentSchoolId.value = parseInt(saved, 10)
    }
    await fetchSchools()
    // 如果保存的学校不存在，选第一个
    if (currentSchoolId.value && !schools.value.find(s => s.id === currentSchoolId.value)) {
      currentSchoolId.value = schools.value[0]?.id || null
    }
    if (currentSchoolId.value) {
      localStorage.setItem('currentSchoolId', currentSchoolId.value)
    }
  }

  return {
    schools,
    currentSchoolId,
    currentSchool,
    fetchSchools,
    setCurrentSchool,
    init,
  }
})
