import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,  // 2分钟，留够排课时间
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：自动附带当前学校 ID
api.interceptors.request.use(config => {
  // 从 localStorage 读取当前学校 ID（避免循环依赖 Pinia store）
  const schoolId = localStorage.getItem('currentSchoolId')
  if (schoolId) {
    config.headers['X-School-ID'] = schoolId
  }
  return config
})

// 响应拦截器
api.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export default api
