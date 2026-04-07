import request from '@/utils/request';

export const getUserInfo = () => request({
  url: '/api/auth/me/',
  method: 'get'
});

export const changePassword = (data) => request({
  url: '/api/auth/change-password/',
  method: 'post',
  data
});
