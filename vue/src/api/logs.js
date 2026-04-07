import request from '@/utils/request';

export const getQueryLogs = (params) => request({
  url: '/api/logs/query/',
  method: 'get',
  params
});

export const getOperationLogs = (params) => request({
  url: '/api/logs/operation/',
  method: 'get',
  params
});
