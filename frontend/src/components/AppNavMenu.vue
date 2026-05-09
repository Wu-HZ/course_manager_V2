<template>
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
defineProps({
  activeMenu: {
    type: String,
    default: '/',
  },
})

const emit = defineEmits(['navigate'])
</script>

<style scoped>
.app-nav-menu {
  border-right: none;
}
</style>
