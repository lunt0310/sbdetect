import { createRouter, createWebHistory } from 'vue-router';
import { ElMessage } from 'element-plus';

import MainLayout from '@/layout/MainLayout.vue';
import { hasAnyRole } from '@/utils/permission';

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: {
      title: '登录'
    }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: {
      title: '注册'
    }
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    meta: {
      requiresAuth: true
    },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: {
          title: '仪表盘',
          requiresAuth: true
        }
      },
      {
        path: 'image-detect',
        name: 'ImageDetect',
        component: () => import('@/views/ImageDetect.vue'),
        meta: {
          title: '图片检测',
          requiresAuth: true
        }
      },
      {
        path: 'video-detect',
        name: 'VideoDetect',
        component: () => import('@/views/VideoDetect.vue'),
        meta: {
          title: '视频检测',
          requiresAuth: true
        }
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/views/History.vue'),
        meta: {
          title: '识别记录',
          requiresAuth: true
        }
      },
      {
        path: 'violations',
        name: 'Violations',
        component: () => import('@/views/Violations.vue'),
        meta: {
          title: '违规记录',
          requiresAuth: true
        }
      },
      {
        path: 'audit-center',
        name: 'AuditCenter',
        component: () => import('@/views/AuditCenter.vue'),
        meta: {
          title: '复核中心',
          requiresAuth: true,
          roles: ['auditor', 'admin']
        }
      },
      {
        path: 'system-logs',
        name: 'SystemLogs',
        component: () => import('@/views/SystemLogs.vue'),
        meta: {
          title: '系统日志',
          requiresAuth: true,
          roles: ['auditor', 'admin']
        }
      },
      {
        path: 'user-manage',
        name: 'UserManage',
        component: () => import('@/views/UserManage.vue'),
        meta: {
          title: '用户管理',
          requiresAuth: true,
          roles: ['admin']
        }
      },
      {
        path: 'history/:id',
        name: 'Detail',
        component: () => import('@/views/Detail.vue'),
        meta: {
          title: '检测详情',
          activeMenu: '/history',
          requiresAuth: true
        }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/Profile.vue'),
        meta: {
          title: '用户中心',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token');
  const userInfo = JSON.parse(localStorage.getItem('user_info') || 'null');
  const role = userInfo?.role || 'user';
  const adminOnlyVisiblePaths = ['/', '/dashboard', '/audit-center'];

  if (to.meta.requiresAuth && !token) {
    next({
      path: '/login',
      query: {
        redirect: to.fullPath
      }
    });
    return;
  }

  if ((to.path === '/login' || to.path === '/register') && token) {
    next('/dashboard');
    return;
  }

  if (to.meta.roles && !hasAnyRole(to.meta.roles, role)) {
    ElMessage.warning('当前账号无权限访问该页面');
    next('/dashboard');
    return;
  }

  if (role === 'admin' && to.meta.requiresAuth && !adminOnlyVisiblePaths.includes(to.path)) {
    ElMessage.warning('管理员端当前仅保留仪表盘与审核页面');
    next('/dashboard');
    return;
  }

  next();
});

router.afterEach((to) => {
  const title = to.meta.title ? `${to.meta.title} - 安全带检测系统` : '安全带检测系统';
  document.title = title;
});

export default router;
