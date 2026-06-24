<template>
  <div
    class="app-shell"
    :class="{ 'app-shell--desktop-open': !isMobile && desktopNavOpen }"
  >
    <aside
      v-if="!isMobile"
      class="app-shell__aside"
      :class="{ 'app-shell__aside--open': desktopNavOpen }"
    >
      <div class="logo">
        <div class="logo__title">排课系统</div>
        <div class="logo__subtitle">Course Manager</div>
      </div>
      <AppNavMenu :active-menu="activeMenu" />
    </aside>

    <button
      v-if="!isMobile"
      type="button"
      class="desktop-nav-toggle"
      :class="{ 'desktop-nav-toggle--open': desktopNavOpen }"
      :aria-label="desktopNavOpen ? '收起侧边导航' : '展开侧边导航'"
      @click="desktopNavOpen = !desktopNavOpen"
    >
      <el-icon>
        <Fold v-if="desktopNavOpen" />
        <Expand v-else />
      </el-icon>
    </button>

    <div class="app-shell__body">
      <header v-if="isMobile" class="app-topbar">
        <el-button class="app-topbar__menu" text circle @click="mobileNavOpen = true">
          <el-icon><Menu /></el-icon>
        </el-button>
        <div class="app-topbar__brand">
          <div class="app-topbar__title">排课系统</div>
          <div class="app-topbar__subtitle">{{ currentPageTitle }}</div>
        </div>
      </header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </div>
  </div>

  <el-drawer
    v-model="mobileNavOpen"
    direction="ltr"
    size="280px"
    class="app-nav-drawer"
    :with-header="false"
  >
    <div class="app-nav-drawer__header">
      <div class="app-nav-drawer__title">排课系统</div>
      <div class="app-nav-drawer__subtitle">选择功能页面</div>
    </div>
    <AppNavMenu :active-menu="activeMenu" @navigate="mobileNavOpen = false" />
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppNavMenu from './components/AppNavMenu.vue'
import { useResponsive } from './composables/useResponsive'

const route = useRoute()
const { isMobile } = useResponsive()
const mobileNavOpen = ref(false)
const desktopNavOpen = ref(true)

const routeTitleMap = {
  '/': '首页概览',
  '/teachers': '教师管理',
  '/classes': '班级管理',
  '/subjects': '课程管理',
  '/locations': '场地管理',
  '/travel-groups': '送教分组',
  '/blocked-times': '教师禁排日',
  '/combined-groups': '校本课程分组',
  '/qualifications': '教师资质',
  '/assignments': '授课分配',
  '/schedule-locks': '课表锁定',
  '/schedule-run': '执行排课',
  '/scheduler-settings': '参数设置',
  '/schedule-view': '课表查看',
  '/observation-assignment': '听课分配',
}

const activeMenu = computed(() => route.path)
const currentPageTitle = computed(() => routeTitleMap[route.path] || '排课系统')

watch(
  () => route.path,
  () => {
    mobileNavOpen.value = false
  }
)
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body,
#app {
  min-height: 100%;
}

body {
  background: #f0f2f5;
  font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.app-shell {
  --app-sidebar-width: 220px;
  min-height: 100vh;
  background: linear-gradient(180deg, #f6f8fb 0%, #eef2f6 100%);
}

.app-shell__aside {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 34;
  width: var(--app-sidebar-width);
  height: 100vh;
  background: #304156;
  box-shadow: 12px 0 30px rgba(34, 52, 74, 0.12);
  transform: translateX(calc(-100% - 24px));
  transition: transform 0.24s ease;
  overflow-y: auto;
}

.app-shell__aside--open {
  transform: translateX(0);
}

.app-shell__body {
  min-width: 0;
  transition: padding-left 0.24s ease;
}

.app-shell--desktop-open .app-shell__body {
  padding-left: var(--app-sidebar-width);
}

.logo {
  display: grid;
  gap: 4px;
  align-content: center;
  min-height: 76px;
  padding: 18px 20px;
  background: linear-gradient(180deg, #263445 0%, #223144 100%);
}

.logo__title {
  color: #fff;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.logo__subtitle {
  color: rgba(191, 203, 217, 0.86);
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.desktop-nav-toggle {
  position: fixed;
  top: 18px;
  left: 14px;
  z-index: 36;
  width: 46px;
  height: 46px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.96);
  color: #223144;
  box-shadow: 0 12px 30px rgba(44, 68, 96, 0.18);
  backdrop-filter: blur(10px);
  cursor: pointer;
  transition: left 0.24s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

.desktop-nav-toggle:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 34px rgba(44, 68, 96, 0.22);
}

.desktop-nav-toggle--open {
  left: calc(var(--app-sidebar-width) - 22px);
}

.app-main {
  min-width: 0;
  padding: 20px;
}

.app-topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(206, 216, 228, 0.9);
  background: rgba(246, 248, 251, 0.95);
  backdrop-filter: blur(10px);
}

.app-topbar__menu {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 8px 20px rgba(59, 82, 109, 0.12);
}

.app-topbar__brand {
  min-width: 0;
}

.app-topbar__title {
  color: #1f2d3d;
  font-size: 17px;
  font-weight: 700;
}

.app-topbar__subtitle {
  margin-top: 2px;
  color: #738295;
  font-size: 12px;
  line-height: 1.4;
}

.app-nav-drawer__header {
  display: grid;
  gap: 4px;
  padding: 16px 18px;
  background: linear-gradient(180deg, #263445 0%, #223144 100%);
}

.app-nav-drawer__title {
  color: #fff;
  font-size: 20px;
  font-weight: 700;
}

.app-nav-drawer__subtitle {
  color: rgba(191, 203, 217, 0.86);
  font-size: 12px;
}

.app-nav-drawer .app-nav-menu {
  height: 100%;
}

.app-nav-drawer .el-menu {
  min-height: calc(100vh - 76px);
}

.app-nav-drawer .el-drawer__body {
  padding: 0;
  background: #304156;
}

@media (max-width: 768px) {
  .app-main {
    padding: 12px;
  }
}
</style>
