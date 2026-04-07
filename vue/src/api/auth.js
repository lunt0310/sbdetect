import request from '@/utils/request';

export const login = (data) => request({
  url: '/api/auth/login/',
  method: 'post',
  data
});

export const register = (data) => request({
  url: '/api/auth/register/',
  method: 'post',
  data
});

export const refreshToken = (refreshTokenValue) => request({
  url: '/api/auth/refresh/',
  method: 'post',
  data: {
    refresh_token: refreshTokenValue
  }
});

export const logout = () => request({
  url: '/api/auth/logout/',
  method: 'post'
});
