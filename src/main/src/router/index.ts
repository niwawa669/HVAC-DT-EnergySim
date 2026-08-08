import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/userStore'

import Login from '@/views/Login.vue'
import Dashboard from '@/views/Dashboard.vue'
import ProjectNew from '@/views/ProjectNew.vue'
import Projects from '@/views/Projects.vue'
import SimulationView from '@/views/SimulationView.vue'
import ResultsView from '@/views/ResultsView.vue'
import AppLayout from '@/components/layout/AppLayout.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Dashboard', component: Dashboard },
      { path: 'project/new', name: 'ProjectNew', component: ProjectNew },
      { path: 'projects', name: 'Projects', component: Projects },
      { path: 'simulation/:taskId', name: 'SimulationView', component: SimulationView },
      { path: 'results/:taskId', name: 'ResultsView', component: ResultsView },
    ],
  },
] as RouteRecordRaw[]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局路由守卫
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  const requiresAuth = to.meta.requiresAuth !== false

  if (requiresAuth && !userStore.isLoggedIn) {
    // 未登录，跳转到登录页，并携带原始目标路径
    next({
      path: '/login',
      query: { redirect: to.fullPath },
    })
  } else if (to.path === '/login' && userStore.isLoggedIn) {
    // 已登录，访问登录页，跳转到首页
    next('/')
  } else {
    next()
  }
})

export default router
