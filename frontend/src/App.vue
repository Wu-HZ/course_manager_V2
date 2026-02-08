<template>
  <el-container class="app-container">
    <el-aside width="200px">
      <div class="logo">
        <h2>排课系统</h2>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
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
          <el-menu-item index="/travel-groups">出差分组</el-menu-item>
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
      </el-menu>
    </el-aside>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
}

.app-container {
  height: 100%;
}

.el-aside {
  background-color: #304156;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #263445;
}

.logo h2 {
  color: #fff;
  font-size: 18px;
}

.el-menu {
  border-right: none;
}

.el-main {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>
