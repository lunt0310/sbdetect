import request from '@/utils/request';

export const getSystemUsers = (params) => request({
  url: '/api/system/users/',
  method: 'get',
  params
});

export const createSystemUser = (data) => request({
  url: '/api/system/users/',
  method: 'post',
  data
});

export const getSystemUserDetail = (id) => request({
  url: `/api/system/users/${id}/`,
  method: 'get'
});

export const updateSystemUser = (id, data) => request({
  url: `/api/system/users/${id}/`,
  method: 'put',
  data
});

export const resetSystemUserPassword = (id, data = {}) => request({
  url: `/api/system/users/${id}/reset-password/`,
  method: 'post',
  data
});
