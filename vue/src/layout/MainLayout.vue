<template>
  <div class="layout-shell">
    <el-container class="layout-container">
      <el-aside width="240px" class="layout-aside">
        <div class="brand-panel">
          <div>
            <h1>安全带检测系统</h1>
            <p>Seat Belt Detection</p>
          </div>
        </div>

        <el-menu
          :default-active="activeMenu"
          class="side-menu"
          router
          unique-opened
        >
          <el-menu-item index="/dashboard">
            <el-icon><House /></el-icon>
            <span>仪表盘</span>
          </el-menu-item>
          <el-menu-item v-if="!isAdminRole" index="/image-detect">
            <el-icon><Picture /></el-icon>
            <span>图片检测</span>
          </el-menu-item>
          <el-menu-item v-if="!isAdminRole" index="/video-detect">
            <el-icon><VideoCamera /></el-icon>
            <span>视频检测</span>
          </el-menu-item>
          <el-menu-item v-if="!isAdminRole" index="/history">
            <el-icon><Tickets /></el-icon>
            <span>识别记录</span>
          </el-menu-item>
          <el-menu-item v-if="!isAdminRole" index="/violations">
            <el-icon><WarningFilled /></el-icon>
            <span>违规记录</span>
          </el-menu-item>
          <el-menu-item v-if="canAudit" index="/audit-center">
            <el-icon><DataBoard /></el-icon>
            <span>{{ isAdminRole ? '复核' : '复核中心' }}</span>
          </el-menu-item>
          <el-menu-item v-if="canAudit && !isAdminRole" index="/system-logs">
            <el-icon><DocumentCopy /></el-icon>
            <span>系统日志</span>
          </el-menu-item>
          <el-menu-item v-if="!isAdminRole" index="/profile">
            <el-icon><User /></el-icon>
            <span>用户中心</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-container class="layout-main-area">
        <el-header class="layout-header">
          <div class="header-left">
            <div class="header-title">{{ route.meta.title }}</div>
          </div>

          <div class="header-right">
            <el-badge
              :is-dot="healthText !== '系统离线'"
              class="status-badge"
              :type="healthBadgeType"
            >
              {{ healthText }}
            </el-badge>
            <el-dropdown @command="handleCommand">
              <div class="user-chip">
                <el-avatar :size="36">{{ userInitial }}</el-avatar>
                <div>
                  <div class="user-name">{{ currentUser?.username || '未登录用户' }}</div>
                  <div class="user-role">{{ roleText }}</div>
                </div>
                <el-icon><ArrowDown /></el-icon>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-if="!isAdminRole" command="profile">个人中心</el-dropdown-item>
                  <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>

        <el-main class="layout-content">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { ElMessage, ElMessageBox } from 'element-plus';

import { getHealthStatus } from '@/api/health';
import { useUserStore } from '@/store/user';
import { isAdmin, isAuditor } from '@/utils/permission';

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const { user: currentUser } = storeToRefs(userStore);
const healthInfo = ref({
  service: '',
  status: 'unknown'
});
let healthTimer = null;

const roleMap = {
  user: '普通用户',
  auditor: '审核员',
  admin: '管理员'
};

const activeMenu = computed(() => route.meta.activeMenu || route.path);
const userInitial = computed(() => (currentUser.value?.username || 'U').slice(0, 1).toUpperCase());
const roleText = computed(() => roleMap[currentUser.value?.role] || currentUser.value?.role || '访客');
const canAudit = computed(() => isAuditor(currentUser.value?.role));
const isAdminRole = computed(() => isAdmin(currentUser.value?.role));
const healthText = computed(() => {
  if (healthInfo.value.status === 'online') {
    return '系统在线';
  }
  return '系统离线';
});
const healthBadgeType = computed(() => {
  if (healthText.value === '系统离线') {
    return 'danger';
  }

  return 'success';
});

const handleCommand = async (command) => {
  if (command === 'profile') {
    router.push('/profile');
    return;
  }

  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确认退出当前登录状态吗？', '退出登录', {
        type: 'warning'
      });
    } catch (error) {
      return;
    }

    await userStore.logoutAction();
    ElMessage.success('已退出登录');
    router.push('/login');
  }
};

const fetchHealth = async () => {
  try {
    await getHealthStatus();
    healthInfo.value = {
      service: '',
      status: 'online'
    };
  } catch (error) {
    healthInfo.value = {
      service: '',
      status: 'offline'
    };
  }
};

onMounted(() => {
  if (!currentUser.value && userStore.accessToken) {
    userStore.fetchUserInfo().catch(() => {});
  }

  fetchHealth();
  healthTimer = window.setInterval(fetchHealth, 60000);
});

onBeforeUnmount(() => {
  if (healthTimer) {
    window.clearInterval(healthTimer);
    healthTimer = null;
  }
});
</script>
