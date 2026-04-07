import axios from 'axios';
import { ElMessage } from 'element-plus';

import router from '@/router';

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_INFO_KEY = 'user_info';
const baseURL = import.meta.env.VITE_API_BASE_URL || '';

const request = axios.create({
  baseURL,
  timeout: 20000
});

const refreshClient = axios.create({
  baseURL,
  timeout: 20000
});

const clearAuthStorage = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_INFO_KEY);
};

const redirectToLogin = () => {
  if (router.currentRoute.value.path !== '/login') {
    router.push('/login');
  }
};

const updateAccessToken = (accessToken) => {
  if (!accessToken) {
    return;
  }

  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);

  const userInfo = JSON.parse(localStorage.getItem(USER_INFO_KEY) || 'null');
  if (userInfo) {
    userInfo.access_token = accessToken;
    localStorage.setItem(USER_INFO_KEY, JSON.stringify(userInfo));
  }
};

const buildApiError = (payload, status) => {
  const error = new Error(payload?.message || '请求失败，请稍后重试');
  error.apiCode = payload?.code;
  error.apiData = payload?.data;
  error.status = status;
  return error;
};

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

request.interceptors.response.use(
  (response) => {
    const payload = response.data;

    if (payload && typeof payload === 'object' && Object.prototype.hasOwnProperty.call(payload, 'code')) {
      if (payload.code === 0) {
        return payload.data;
      }

      const message = payload.message || '请求失败，请稍后重试';

      if (payload.code === 401) {
        clearAuthStorage();
        redirectToLogin();
      }

      ElMessage.error(message);
      return Promise.reject(buildApiError(payload, response.status));
    }

    return payload;
  },
  async (error) => {
    const status = error.response?.status;
    const originalRequest = error.config || {};
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    const errorPayload = error.response?.data;
    const serverMessage = error.response?.data?.message
      || error.response?.data?.detail
      || error.response?.data?.error;

    if (
      status === 401
      && refreshToken
      && !originalRequest._retry
      && !originalRequest.url?.includes('/api/auth/refresh/')
      && !originalRequest.url?.includes('/api/auth/login/')
      && !originalRequest.url?.includes('/api/auth/register/')
    ) {
      originalRequest._retry = true;

      try {
        const refreshResponse = await refreshClient.post('/api/auth/refresh/', {
          refresh_token: refreshToken
        });
        const refreshPayload = refreshResponse.data;

        if (refreshPayload?.code === 0 && refreshPayload?.data?.access_token) {
          updateAccessToken(refreshPayload.data.access_token);
          originalRequest.headers = originalRequest.headers || {};
          originalRequest.headers.Authorization = `Bearer ${refreshPayload.data.access_token}`;
          return request(originalRequest);
        }
      } catch (refreshError) {
        clearAuthStorage();
        redirectToLogin();
        ElMessage.error(refreshError.response?.data?.message || '登录状态已失效，请重新登录');
        return Promise.reject(refreshError);
      }
    }

    if (status === 401) {
      clearAuthStorage();
      redirectToLogin();
    }

    if (errorPayload && typeof errorPayload === 'object' && Object.prototype.hasOwnProperty.call(errorPayload, 'code')) {
      ElMessage.error(errorPayload.message || '请求失败，请稍后重试');
      return Promise.reject(buildApiError(errorPayload, status));
    }

    ElMessage.error(serverMessage || '请求失败，请稍后重试');
    return Promise.reject(error);
  }
);

export { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, USER_INFO_KEY, clearAuthStorage, updateAccessToken };
export default request;
