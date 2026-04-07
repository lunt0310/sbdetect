import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { login, logout, register } from '@/api/auth';
import { getUserInfo } from '@/api/user';
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, USER_INFO_KEY, clearAuthStorage } from '@/utils/request';

export const useUserStore = defineStore('user', () => {
  const accessToken = ref(localStorage.getItem(ACCESS_TOKEN_KEY) || '');
  const refreshToken = ref(localStorage.getItem(REFRESH_TOKEN_KEY) || '');
  const user = ref(JSON.parse(localStorage.getItem(USER_INFO_KEY) || 'null'));

  const isLoggedIn = computed(() => Boolean(accessToken.value));

  const setAuth = (payload) => {
    const data = payload || {};
    accessToken.value = data.access_token || '';
    refreshToken.value = data.refresh_token || refreshToken.value || '';
    user.value = data;

    if (accessToken.value) {
      localStorage.setItem(ACCESS_TOKEN_KEY, accessToken.value);
    }

    if (refreshToken.value) {
      localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken.value);
    }

    localStorage.setItem(USER_INFO_KEY, JSON.stringify(user.value));
  };

  const clearAuth = () => {
    accessToken.value = '';
    refreshToken.value = '';
    user.value = null;
    clearAuthStorage();
  };

  const loginAction = async (payload) => {
    const data = await login(payload);
    setAuth(data || {});
    return data;
  };

  const registerAction = async (payload) => {
    const data = await register(payload);
    setAuth(data || {});
    return data;
  };

  const fetchUserInfo = async () => {
    const data = await getUserInfo();
    const mergedUser = {
      ...(user.value || {}),
      ...(data || {})
    };

    user.value = mergedUser;
    localStorage.setItem(USER_INFO_KEY, JSON.stringify(mergedUser));
    return mergedUser;
  };

  const logoutAction = async () => {
    try {
      await logout();
    } finally {
      clearAuth();
    }
  };

  return {
    accessToken,
    refreshToken,
    user,
    isLoggedIn,
    setAuth,
    clearAuth,
    loginAction,
    registerAction,
    fetchUserInfo,
    logoutAction
  };
});
