import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue')
  },
  {
    path: '/teachers',
    name: 'Teachers',
    component: () => import('../views/TeacherList.vue')
  },
  {
    path: '/classes',
    name: 'Classes',
    component: () => import('../views/ClassList.vue')
  },
  {
    path: '/subjects',
    name: 'Subjects',
    component: () => import('../views/SubjectList.vue')
  },
  {
    path: '/locations',
    name: 'Locations',
    component: () => import('../views/LocationList.vue')
  },
  {
    path: '/travel-groups',
    name: 'TravelGroups',
    component: () => import('../views/TravelGroupList.vue')
  },
  {
    path: '/qualifications',
    name: 'Qualifications',
    component: () => import('../views/QualificationList.vue')
  },
  {
    path: '/assignments',
    name: 'Assignments',
    component: () => import('../views/AssignmentList.vue')
  },
  {
    path: '/schedule-run',
    name: 'ScheduleRun',
    component: () => import('../views/ScheduleRun.vue')
  },
  {
    path: '/schedule-locks',
    name: 'ScheduleLocks',
    component: () => import('../views/ScheduleLockList.vue')
  },
  {
    path: '/schedule-view',
    name: 'ScheduleView',
    component: () => import('../views/ScheduleView.vue')
  },
  {
    path: '/scheduler-settings',
    name: 'SchedulerSettings',
    component: () => import('../views/SchedulerSettings.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
