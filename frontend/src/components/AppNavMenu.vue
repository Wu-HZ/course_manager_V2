<template>
  <div class="app-nav-school">
    <el-select
      :model-value="schoolStore.currentSchoolId"
      size="small"
      popper-class="school-select-popper"
      @change="schoolStore.setCurrentSchool"
      @visible-change="(v) => v && schoolStore.fetchSchools()"
    >
      <el-option
        v-for="s in schoolStore.schools"
        :key="s.id"
        :label="s.short_name || s.name"
        :value="s.id"
      />
    </el-select>
  </div>

  <el-menu
    :default-active="activeMenu"
    :default-openeds="['data']"
    router
    background-color="#304156"
    text-color="#bfcbd9"
    active-text-color="#409EFF"
    class="app-nav-menu"
    @select="emit('navigate')"
  >
    <el-menu-item index="/">
      <el-icon><House /></el-icon>
      <span>首页</span>
    </el-menu-item>
    <el-menu-item index="/schools">
      <el-icon><School /></el-icon>
      <span>学校管理</span>
    </el-menu-item>
    <el-sub-menu index="data">
      <template #title>
        <el-icon><Files /></el-icon>
        <span>数据管理</span>
      </template>
      <el-menu-item index="/teachers">教师管理</el-menu-item>
      <el-menu-item index="/classes">班级管理</el-menu-item>
      <el-menu-item index="/subjects">课程管理</el-menu-item>
      <el-menu-item index="/locations">场地管理</el-menu-item>
      <el-menu-item index="/travel-groups">送教分组</el-menu-item>
      <el-menu-item index="/blocked-times">教师禁排日</el-menu-item>
      <el-menu-item index="/combined-groups">校本课程分组</el-menu-item>
      <el-menu-item index="/qualifications">教师资质</el-menu-item>
      <el-menu-item index="/assignments">授课分配</el-menu-item>
      <el-menu-item index="/schedule-locks">课表锁定</el-menu-item>
    </el-sub-menu>
    <el-menu-item index="/schedule-run">
      <el-icon><VideoPlay /></el-icon>
      <span>执行排课</span>
    </el-menu-item>
    <el-menu-item index="/scheduler-settings">
      <el-icon><Setting /></el-icon>
      <span>参数设置</span>
    </el-menu-item>
    <el-menu-item index="/schedule-view">
      <el-icon><Calendar /></el-icon>
      <span>课表查看</span>
    </el-menu-item>
    <el-menu-item index="/observation-assignment">
      <el-icon><Notebook /></el-icon>
      <span>听课分配</span>
    </el-menu-item>
  </el-menu>
</template>

<script setup>
import { useSchoolStore } from '../stores/school'

defineProps({
  activeMenu: {
    type: String,
    default: '/',
  },
})

const emit = defineEmits(['navigate'])
const schoolStore = useSchoolStore()
</script>

<style scoped>
.app-nav-school {
  padding: 10px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.app-nav-school :deep(.el-select) {
  width: 100%;
}

.app-nav-school :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  box-shadow: none;
}

.app-nav-school :deep(.el-input__inner) {
  color: #bfcbd9;
}

.app-nav-menu {
  border-right: none;
}
</style>
