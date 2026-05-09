import { computed, onMounted, readonly, ref } from 'vue'

const MOBILE_BREAKPOINT = 768
const TABLET_BREAKPOINT = 992
const viewportWidth = ref(typeof window === 'undefined' ? 1280 : window.innerWidth)

let initialized = false

const syncViewportWidth = () => {
  viewportWidth.value = window.innerWidth
}

const ensureViewportListener = () => {
  if (initialized || typeof window === 'undefined') {
    return
  }
  initialized = true
  syncViewportWidth()
  window.addEventListener('resize', syncViewportWidth, { passive: true })
}

export const useResponsive = () => {
  onMounted(ensureViewportListener)

  return {
    viewportWidth: readonly(viewportWidth),
    isMobile: computed(() => viewportWidth.value <= MOBILE_BREAKPOINT),
    isTablet: computed(() => viewportWidth.value <= TABLET_BREAKPOINT),
  }
}
